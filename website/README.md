# ArchAI website

Static site (HTML, CSS, vanilla JS; no build step, no frameworks). Deployed on
Vercel together with the MkDocs documentation: the website at `/`, the docs at
`/docs/`.

```
website/
  index.html             landing
  agents.html            the agent family, decision table, demos
  case-studies.html      case studies
  research.html          papers
  assets/css/site.css    design system (paper, ink, ArchAI orange #FF7A1A)
  assets/js/data.js      ALL content: families, agents, decisions, case studies, papers
  assets/js/transcripts.js  real CLI output for the Proof-family demos (generated)
  assets/js/site.js      rendering, terminal player, halftone, reveal, marquee
  assets/icons/          agent icons and family badges (generated)
  demo/                  standards config used by the "ArchAI on ArchAI" case study
```

## Editing content

Everything on the pages comes from `assets/js/data.js`. To add an agent, case
study or paper, add one entry to the matching list; no HTML or layout changes
are needed.

Content rules:

- **Proof-family demos use real output** from `transcripts.js`. Never type
  numbers into it by hand; regenerate it (below).
- **Other demos** are marked `illustrative: true` and are shown with
  "Illustrative: AI output varies."
- **Case-study facts** name the commit they were measured at.
- **Claims to avoid:** customer results, accuracy or speed benchmarks,
  guarantees, support for languages other than Python, and any affiliation
  with Google or Anthropic.

## Regenerating the terminal transcripts

```bash
python scripts/capture_website_transcripts.py --at b16b750 \
    --okf-samples path/to/open-knowledge-format/bundles
```

`--at` measures a clean temporary clone of that commit, so the output is not
marked `(dirty)`. `--okf-samples` points at the `bundles/` folder of
[GoogleCloudPlatform/open-knowledge-format](https://github.com/GoogleCloudPlatform/open-knowledge-format).

## Regenerating icons

```bash
python scripts/build_agent_icons.py      # writes assets/icons/*.svg and icons/sheet.html
```

Glyphs are 16×16 bitmaps in the script. Proof agents sit on solid orange;
Insight agents get a dashed frame (AI-assisted).

## Preview and build

```bash
python scripts/build_site.py --serve     # builds site/ and serves http://127.0.0.1:8000
```

Append `?static` to any page URL to see its final state without animation.
That is the same view visitors get with "reduce motion" enabled. Mockup
screenshots of every page (desktop 1440px, mobile 390px) are in
`design/mockups/`.
