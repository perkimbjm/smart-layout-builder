# Prompt — Template Recommendation

> **ID:** `slb.prompt.template_recommendation`
> **Version:** v1
> **Output schema:** `ai/schemas/template_recommendation.schema.json`
> **Recommended models:** GPT-4o-mini, Claude Haiku (lightweight retrieval task)
> **Temperature:** 0.2
> **Max tokens:** 700

---

## Purpose

Given a project snapshot + user intent + the catalog of installed templates (and optionally marketplace listings), recommend the **top 1–3 templates** most likely to fit. Reasoning includes audience match, paper size match, language match, density, and topic match.

This is a *retrieval + ranking* task, not a generative one. Embeddings can power a pre-filter; this prompt ranks the candidates.

---

## System Prompt

```
You are a template librarian. Given a project snapshot and a candidate set of
templates, rank the top matches and explain why.

You output JSON only:
  - ranked: ordered list of {template_id, score, reason}
  - explanation: 1–2 sentences summarizing the ranking strategy

Scoring weights (you may tune):
  - audience_match  : 0.30
  - language_match  : 0.20
  - paper_match     : 0.15
  - density_match   : 0.10
  - topic_keywords  : 0.15
  - quality/usage   : 0.10

If no candidate scores ≥ 0.5, return an empty `ranked` list and explain.
```

---

## User Prompt Template

```
PROJECT
-------
title: {{project.title}}
purpose: {{intent.purpose}}
audience: {{intent.audience}}
locale: {{intent.locale}}
density: {{intent.density}}
paper: {{intent.paper}} {{intent.orientation}}
keywords: {{project.keywords_json}}    # auto-extracted from layer names / titles

CANDIDATES (already pre-filtered to relevant)
---------------------------------------------
{{#each candidates}}
- template_id: {{this.template_id}}
  name: "{{this.name}}"
  description: "{{this.description}}"
  paper: {{this.paper}} {{this.orientation}}
  languages: {{this.languages_json}}
  audience: {{this.audience}}
  density: {{this.density}}
  tags: {{this.tags_json}}
  install_count: {{this.install_count}}
  rating: {{this.rating}}
{{/each}}
```

---

## Output JSON Schema (abbreviated)

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["ranked", "explanation", "diagnostics"],
  "properties": {
    "ranked": {
      "type": "array",
      "maxItems": 3,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["template_id", "score", "reason"],
        "properties": {
          "template_id": {"type": "string"},
          "score": {"type": "number", "minimum": 0, "maximum": 1},
          "reason": {"type": "string", "maxLength": 240}
        }
      }
    },
    "explanation": {"type": "string", "maxLength": 400},
    "diagnostics": {
      "type": "object",
      "properties": {
        "candidates_considered": {"type": "integer"},
        "min_score_threshold": {"type": "number"}
      }
    }
  }
}
```

---

## Few-Shot Example

### Input

```
PROJECT
title: "Peta Risiko Banjir Kelurahan Banjar Selatan"
purpose: atlas
audience: government
locale: id-ID
density: balanced
paper: A3 landscape
keywords: ["banjir","risiko","kelurahan","banjarmasin"]

CANDIDATES
- template_id: "org.id.bpbd.atlas-a3"
  name: "BPBD Atlas A3"
  description: "Template atlas peta bencana untuk BPBD Indonesia."
  paper: A3 landscape
  languages: ["id","en"]
  audience: government
  density: balanced
  tags: ["disaster","bpbd","indonesia","atlas"]
  install_count: 312, rating: 4.7
- template_id: "io.minimal.a4"
  name: "Minimal A4"
  description: "Minimalist single-sheet layout."
  paper: A4 portrait
  languages: ["en"]
  audience: casual
  density: minimal
  tags: ["minimal","compact"]
  install_count: 5400, rating: 4.4
- template_id: "edu.academic-figure"
  name: "Academic Figure"
  description: "Journal figure layout, monochrome."
  paper: A4 portrait
  languages: ["en"]
  audience: academic
  density: rich
  tags: ["journal","monochrome","figure"]
  install_count: 220, rating: 4.6
```

### Output

```json
{
  "ranked": [
    {
      "template_id": "org.id.bpbd.atlas-a3",
      "score": 0.94,
      "reason": "Direct match on audience (government), language (id), paper (A3 landscape), atlas purpose, and disaster-domain tags."
    }
  ],
  "explanation": "Only one candidate clears the threshold. The other two mismatch on audience, language, paper, or purpose.",
  "diagnostics": {
    "candidates_considered": 3,
    "min_score_threshold": 0.5
  }
}
```

---

## Consumer Logic

```python
result = ai.complete(req).parsed_json
top = result["ranked"][:1]
if not top:
    # Fall back to built-in heuristic ranker.
    top = heuristic.rank(project, candidates)[:1]
ui.show_recommendation(top, explanation=result["explanation"])
```

---

## Pre-filtering (before sending to AI)

The pre-filter (deterministic) reduces candidates **before** they hit the AI:

1. Drop templates whose `paper` is incompatible (unless `orientation` flip allowed).
2. Drop templates with no overlap on `languages`.
3. Drop templates marked `deprecated`.
4. If embeddings are enabled, cosine-similarity tag/keyword match → keep top 8.

Then send the surviving 5–8 candidates to this prompt.

---

## When NOT to call

- User has explicitly pinned a default preset/template — respect it.
- No installed templates and Marketplace disabled — nothing to recommend.
- User intent is "free composition" (no preset) — recommendation would be noise.

---

## Privacy

- Only sanitized project metadata is sent (title, locale, audience, keywords).
- No layer data, no file paths.
- The candidate catalog is local; nothing about the user's installed templates leaks beyond ids and public metadata.
