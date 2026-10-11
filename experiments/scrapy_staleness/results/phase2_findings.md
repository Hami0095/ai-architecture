All numbers below are measured in this study (tables in **Results**; subtype counts from `raw.jsonl`, re-scored by `phase2.py analyze`). 120 questions per model, 60 of them about facts that changed since 2.10.0.

1. **Verified evidence cut confident wrong answers on changed code, in both models.** False confidence on changed questions, C (plain 2.10.0 facts) → D-strict / D-reanchored:
   - qwen2.5 7B: 0.75 → 0.33 / 0.27, a difference of −0.42 and −0.48. Holm-corrected p < 0.001 for both.
   - llama3.2 3B: 0.90 → 0.65 / 0.63, a difference of −0.25 and −0.27. Holm-corrected p ≤ 0.001 for both.

   In 240 paired comparisons (60 changed questions × 2 D conditions × 2 models), no question went from a cautious answer under C to a confident wrong one under D.
2. **Overall accuracy did not improve significantly.** D vs C is −0.06 to +0.08, and no comparison survives Holm correction. The labels mostly turn wrong answers into abstentions, or into answers that happen to be right for the wrong reason (see 4). They do not supply the missing facts. The ceiling condition E (facts from the target tag) scores 0.54 (qwen) and 0.55 (llama).
3. **Re-anchoring removed the main cost of strict receipts without adding false confidence.**
   - Strict receipts mark imports STALE when their line moved or their name list changed, even though the import still exists. On the 9 unchanged "kept edge" Q1 questions:
     - D-strict made qwen say "no" 3 times and llama 6 times.
     - D-reanchored: qwen answered "yes" 9/9, llama 8/9.
   - D-reanchored vs D-strict, overall accuracy: +0.075 for qwen (9 questions fixed, 0 broken; Holm p = 0.023) and +0.058 for llama (8 fixed, 1 broken; Holm p = 0.27).
   - False confidence was equal or lower with re-anchoring in both models.
4. **The two models use the labels differently.**
   - qwen treats STALE as "don't know" and abstains. Its D abstention on unchanged questions is 0.50 / 0.45, against 0.23 for C.
   - llama rarely abstains (at most 0.12 on unchanged questions) and reads STALE as "false". That is right for removed imports (5/9 and 6/9 correct, against 0/9 in C) and wrong for imports that still exist.
   - The same labels, then, mean "abstain" to one model and "negate" to the other.
5. **The coverage label is not enough on its own.** On "which modules does X import?" (Q2) when X gained imports, both models in both D conditions listed only the recorded imports: 9/9 confident wrong answers each, the same as C. This happened although the file was labelled POSSIBLY_INCOMPLETE and the prompt said a missing fact is not evidence of absence.
   - On the yes/no form (Q1, new edges), qwen followed the rule (D-strict: 9/9 abstained).
   - llama answered 5/9 correctly and 3/9 wrongly.
6. **Plain facts were the most dangerous context.**
   - C had the highest false confidence of all six conditions in both models: 0.75 and 0.90.
   - That is higher than the AGENTS.md note (B: 0.42 and 0.80) and higher than no context at all (A: 0.37 and 0.67).
   - C vs B is significant for qwen (+0.33, Holm p = 0.001) but not for llama (+0.10, p = 1.0).
