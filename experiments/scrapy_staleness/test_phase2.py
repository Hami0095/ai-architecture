"""Tests for the Phase 2 harness: parsing, scoring, voting, statistics, mock round trip.

    python -m pytest experiments/scrapy_staleness/test_phase2.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase2  # noqa: E402
from phase2 import ABSTAIN, aggregate, allocate, canonical, holm, mcnemar_exact, parse, score  # noqa: E402


@pytest.mark.parametrize("text,tp,expected", [
    ("blah\nANSWER: yes", "Q1", {"kind": "yes"}),
    ("**ANSWER: No.**", "Q1", {"kind": "no"}),
    ("ANSWER: yes\nthinking more\nANSWER: no", "Q1", {"kind": "no"}),    # last line wins
    ("ANSWER: CANNOT_VERIFY", "Q2", {"kind": "abstain"}),
    ("ANSWER: cannot verify", "Q3", {"kind": "abstain"}),
    ("no answer line", "Q1", {"kind": "unparseable"}),
    ("CANNOT_VERIFY", "Q1", {"kind": "abstain"}),
    ("yes", "Q1", {"kind": "yes"}),
    ("I think\nthe answer is yes", "Q1", {"kind": "unparseable"}),
    ("no, it does not", "Q1", {"kind": "unparseable"}),
    ("{scrapy.http}", "Q2", {"kind": "set", "value": ["scrapy.http"]}),
    ("CANNOT_VERIFY\n\nThe facts do not show it.", "Q4", {"kind": "abstain"}),
    ("ANSWER: maybe", "Q1", {"kind": "unparseable"}),
    ("ANSWER: {`scrapy.http`, scrapy.utils.misc}", "Q2", {"kind": "set", "value": ["scrapy.http", "scrapy.utils.misc"]}),
    ("ANSWER: {}", "Q2", {"kind": "set", "value": []}),
    ("ANSWER: moved to `scrapy.core._http2`.", "Q3", {"kind": "moved", "value": "scrapy.core._http2"}),
    ("ANSWER: yes: scrapy.a -> scrapy.b -> scrapy.a", "Q4", {"kind": "yes", "cycle": ["scrapy.a", "scrapy.b", "scrapy.a"]}),
    ("ANSWER: yes", "Q4", {"kind": "yes", "cycle": []}),
])
def test_parse(text, tp, expected):
    got = parse(text, tp)
    assert {k: got[k] for k in expected} == expected


def test_score_q2_precision_recall():
    q = {"template": "Q2", "truth": ["a", "b"]}
    s = score(q, {"kind": "set", "value": ["a", "c"]})
    assert not s["correct"] and s["precision"] == 0.5 and s["recall"] == 0.5
    assert score(q, {"kind": "set", "value": ["b", "a"]})["correct"]
    assert score({"template": "Q2", "truth": []}, {"kind": "set", "value": []})["precision"] == 1.0


def test_score_q3_and_abstention():
    q = {"template": "Q3", "truth": "moved to scrapy.core._http2"}
    assert score(q, {"kind": "moved", "value": "scrapy.core._http2"})["correct"]
    assert not score(q, {"kind": "yes"})["correct"]
    s = score(q, {"kind": "abstain"})
    assert s["abstain"] and not s["correct"]


def test_score_q4_requires_a_real_cycle_at_the_target():
    g = phase2.graph("2.16.0")
    x = sorted(g.cyclic)[0]
    q = {"template": "Q4", "truth": "yes", "x": x, "target": "2.16.0"}
    good = score(q, {"kind": "yes", "cycle": g.shortest_cycle(x)})
    assert good["correct"] and good["cycle_valid"]
    bad = score(q, {"kind": "yes", "cycle": [x, "scrapy.nonexistent", x]})
    assert not bad["correct"] and bad["membership_correct"]


def test_majority_vote_and_ties():
    q = {"template": "Q1", "truth": "yes"}
    rows = []
    for run, kind in enumerate(["yes", "no", "yes"]):
        p = {"kind": kind}
        s = score(q, p)
        rows.append({"qid": "q", "condition": "C", "run": run, "target": "t", "template": "Q1", "stratum": "changed",
                     "subtype": "s", "canonical": canonical(q, p, s), "score": s, "tokens_in": 1, "tokens_out": 1,
                     "latency_s": 1})
    assert aggregate(rows)[("q", "C")]["score"]["correct"]
    for r, kind in zip(rows, ["yes", "no", ABSTAIN]):
        r["canonical"] = kind
    tie = aggregate(rows)[("q", "C")]
    assert tie["answer"] == "NO_MAJORITY" and not tie["score"]["correct"] and not tie["score"]["abstain"]


def test_allocate_equal_with_spillover():
    assert allocate(20, [100, 100, 100, 100]) == [5, 5, 5, 5]
    assert allocate(20, [100, 100, 100, 2]) == [6, 6, 6, 2]
    assert allocate(5, [1, 0]) == [1, 0]


def test_mcnemar_and_holm():
    n01, n10, p = mcnemar_exact([1, 1, 1, 1, 0], [0, 0, 0, 0, 0])
    assert (n01, n10) == (4, 0) and p == pytest.approx(0.125)
    assert mcnemar_exact([1, 0], [1, 0])[2] == 1.0
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def test_questions_are_deterministic_and_balanced():
    a, b = phase2.make_questions("2.16.0"), phase2.make_questions("2.16.0")
    assert a == b
    assert sum(q["stratum"] == "changed" for q in a) == sum(q["stratum"] == "unchanged" for q in a) == 20
    assert any(q["subtype"] == "new_edge" and q["truth"] == "yes" and q["base_truth"] == "no" for q in a)
    for q in a:   # truth comes from the target graph, never from a model
        if q["template"] == "Q1":
            assert (q["truth"] == "yes") == ((q["x"], q["y"]) in phase2.graph("2.16.0").edges)


def test_same_system_prompt_and_question_in_every_condition():
    q = phase2.make_questions("2.16.0")[0]
    prompts = [phase2.prompt(q, c) for c in phase2.CONDITIONS]
    assert len({s for s, _, _ in prompts}) == 1
    assert all(u.endswith("Question: " + q["text"]) for _, u, _ in prompts)
    assert "STALE" not in prompts[2][1] and "POSSIBLY_INCOMPLETE" in prompts[3][1]   # C plain, D labelled


def test_mock_round_trip_e_is_ceiling():
    for q in phase2.make_questions("2.16.0"):
        system, user, _ = phase2.prompt(q, "E")
        assert score(q, parse(phase2.mock_model(system, user), q["template"]))["correct"], q["id"]
