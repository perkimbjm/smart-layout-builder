# Prompt — Layout Generation

> **ID:** `slb.prompt.layout_generation`
> **Version:** v1
> **Output schema:** `ai/schemas/layout_proposal.schema.json`
> **Recommended models:** GPT-4o, Claude Opus/Sonnet, local Llama-3.1-70B
> **Temperature:** 0.2 (deterministic-ish)
> **Max tokens:** 1500

---

## Purpose

Given a structured snapshot of a QGIS project + a paper specification + user intent, propose a complete layout composition: which cartographic items to include, where they live on the page, and what styling tokens they should use. The output is consumed by the deterministic `ConstraintSolver`, which is the final source of truth for placement.

---

## System Prompt

```
You are a senior cartographer assisting a GIS analyst inside the QGIS print-layout
workflow. You produce structured JSON layout proposals only — never prose.

You optimize for:
1. Cartographic correctness: scale bar matches map units; north arrow honored when CRS
   is projected; legend never lists invisible/out-of-extent layers.
2. Visual balance: hierarchy with one dominant element (the map), supporting elements
   sized proportionally, generous but not wasteful whitespace.
3. Audience fit: government / consulting / academic / casual — adapt tone of titles
   and density of decoration accordingly.
4. Adherence to constraints: paper, orientation, locked items, brand tokens.

You NEVER invent layers, attributes, or data the user did not provide.
You NEVER place items so they overlap.
You ALWAYS keep a margin of at least the paper's "safe_margin_mm" value from edges.

Your output MUST be a single JSON object matching the schema provided. No code fences.
No commentary. If you cannot honor a constraint, return a JSON object with an
`unmet_constraints` array explaining why.
```

---

## User Prompt Template

```
PROJECT SNAPSHOT (sanitized)
---------------------------
title: {{project.title}}
crs: {{project.crs}}
extent: {{project.extent}}     # in project CRS
layers:
{{#each project.layers}}
  - id: {{this.id}}
    role: {{this.role}}        # background | thematic | overlay | label
    geometry_type: {{this.geometry_type}}
    visible: {{this.visible}}
    feature_count_in_extent: {{this.feature_count_in_extent}}
    style_class: {{this.style_class}}
{{/each}}

PAPER
-----
size: {{paper.size}}            # A4, A3, Letter, ...
orientation: {{paper.orientation}}
width_mm: {{paper.width_mm}}
height_mm: {{paper.height_mm}}
safe_margin_mm: {{paper.safe_margin_mm}}

USER INTENT
-----------
audience: {{intent.audience}}   # government | consulting | academic | casual
purpose: {{intent.purpose}}     # one-shot | atlas | report-figure | presentation
density: {{intent.density}}     # minimal | balanced | rich
language: {{intent.locale}}     # en-US, id-ID, ...

BRAND TOKENS (optional)
-----------------------
{{brand_json}}

LOCKED ITEMS (do not move/remove)
---------------------------------
{{locked_items_json}}
```

---

## Output JSON Schema (abbreviated)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "LayoutProposal",
  "type": "object",
  "additionalProperties": false,
  "required": ["items", "diagnostics"],
  "properties": {
    "items": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["role", "x_mm", "y_mm", "w_mm", "h_mm"],
        "properties": {
          "role": {
            "type": "string",
            "enum": [
              "map", "title", "subtitle", "legend", "scale_bar",
              "north_arrow", "attribution", "inset_map", "logo",
              "footer", "grid_label", "spacer"
            ]
          },
          "x_mm": {"type": "number", "minimum": 0},
          "y_mm": {"type": "number", "minimum": 0},
          "w_mm": {"type": "number", "exclusiveMinimum": 0},
          "h_mm": {"type": "number", "exclusiveMinimum": 0},
          "style": {"type": "object"},
          "bindings": {
            "type": "object",
            "patternProperties": {".*": {"type": "string"}}
          },
          "rationale": {"type": "string", "maxLength": 240}
        }
      }
    },
    "diagnostics": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "strategy_used": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "unmet_constraints": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    }
  }
}
```

---

## Few-Shot Example

### Input

```json
{
  "project": {
    "title": "Risk Map — Kelurahan Banjar Selatan",
    "crs": "EPSG:23834",
    "extent": [3306500, 9637800, 3309200, 9640500],
    "layers": [
      {"id":"basemap","role":"background","geometry_type":"raster",
       "visible":true,"feature_count_in_extent":1,"style_class":"orthophoto"},
      {"id":"flood","role":"thematic","geometry_type":"polygon",
       "visible":true,"feature_count_in_extent":42,"style_class":"hazard_red"},
      {"id":"boundary","role":"overlay","geometry_type":"polygon",
       "visible":true,"feature_count_in_extent":1,"style_class":"thin_black"}
    ]
  },
  "paper": {"size":"A3","orientation":"landscape",
            "width_mm":420,"height_mm":297,"safe_margin_mm":12},
  "intent": {"audience":"government","purpose":"atlas",
             "density":"balanced","locale":"id-ID"}
}
```

### Output

```json
{
  "items": [
    {"role":"map","x_mm":12,"y_mm":24,"w_mm":280,"h_mm":250,
     "style":{"grid":"true","grid_interval_m":500},
     "bindings":{},
     "rationale":"Dominant left two-thirds, square-ish, includes 500m grid."},
    {"role":"title","x_mm":12,"y_mm":8,"w_mm":396,"h_mm":12,
     "style":{"font_size_pt":18,"weight":"bold"},
     "bindings":{"text":"[%@project_title%]"},
     "rationale":"Full-width title bar with project title binding."},
    {"role":"legend","x_mm":300,"y_mm":24,"w_mm":108,"h_mm":120,
     "style":{"columns":1,"title":"Legenda"},
     "bindings":{},
     "rationale":"Right column, top. ID locale title."},
    {"role":"scale_bar","x_mm":300,"y_mm":150,"w_mm":108,"h_mm":12,
     "style":{"segments":4,"units":"meters","style":"line_ticks"},
     "bindings":{},
     "rationale":"Below legend; meters because projected CRS."},
    {"role":"north_arrow","x_mm":300,"y_mm":166,"w_mm":24,"h_mm":24,
     "style":{"variant":"slim","auto_rotate":true},
     "bindings":{},
     "rationale":"Compact slim variant; auto-rotate honors true north."},
    {"role":"attribution","x_mm":300,"y_mm":260,"w_mm":108,"h_mm":12,
     "style":{"font_size_pt":7},
     "bindings":{"text":"Sumber data: {sources}"},
     "rationale":"Below legend stack."}
  ],
  "diagnostics": {
    "strategy_used": "two_column_atlas",
    "confidence": 0.86,
    "unmet_constraints": []
  }
}
```

---

## Failure Modes & Validation

| Failure | Detection | Action |
|---------|-----------|--------|
| JSON parse fails | `json.loads` | Retry once with `temperature=0`. Then fall back to deterministic strategy. |
| Schema validation fails | `jsonschema.validate` | Show "AI returned malformed proposal — using fallback" banner. |
| Items overlap | `ConstraintSolver.detect_overlaps()` | Solver attempts repair; if irrecoverable, fallback. |
| Item escapes paper | Solver checks bounds | Same as above. |
| Hallucinated layer id | `bridge.visible_layer_ids()` | Strip; log warning. |
| Empty `items` array | Schema (`minItems:1`) | Hard fail; fallback. |

---

## Sanitization Before Sending

Before this prompt leaves the user's machine, the project snapshot is run through `ai/sanitizer.py`:

- Layer paths → stripped to filename only.
- Project file path → omitted.
- User name in attribution defaults → replaced with `<user>`.
- Hostnames / URLs → `<external>`.
- Any string matching `email|phone|ID number` regex → redacted.

The sanitized snapshot is hashed for cache lookup.

---

## Versioning

Bump version when:
- Schema changes (additive ok in MINOR).
- System prompt instructions change in a behavior-affecting way.

Old prompt versions are retained at `ai/prompts/archive/layout_generation/vN.md`.
