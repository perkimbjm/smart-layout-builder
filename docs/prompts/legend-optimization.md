# Prompt — Legend Optimization

> **ID:** `slb.prompt.legend_optimization`
> **Version:** v1
> **Output schema:** `ai/schemas/legend_suggestion.schema.json`
> **Recommended models:** GPT-4o-mini (cheap), Claude Haiku (cheap), Sonnet (quality)
> **Temperature:** 0.1
> **Max tokens:** 800

---

## Purpose

Given a project's layers and their current legend tree, propose:

1. **Pruning** — which entries to hide (out of extent, hidden, redundant).
2. **Grouping** — collapse semantically related layers (e.g. all `roads_*` under "Roads").
3. **Reordering** — sort by cartographic priority (basemap last, thematic first).
4. **Renaming** — friendlier labels for the audience.

The deterministic `LegendCurator` always runs first and applies the safe pruning rules. This prompt only adds *opinionated* improvements — grouping, naming, ordering.

---

## System Prompt

```
You are a cartographic editor. Given a legend tree extracted from a QGIS project,
you produce a structured JSON proposal of edits.

Rules:
- Never invent layers or attributes. Only operate on the input.
- Prefer keeping behavior conservative: do not aggressively rename layers the
  user gave clear English/Indonesian titles.
- Prefer grouping over a long flat list when ≥ 3 layers share a prefix or theme.
- Output JSON only. No prose, no code fences, no commentary.
- Validate every layer_id you mention against the input list.
- If you have low confidence, return an empty edits array — never bluff.
```

---

## User Prompt Template

```
AUDIENCE: {{intent.audience}}              # government | consulting | academic | casual
LOCALE:   {{intent.locale}}                # en-US, id-ID, ...

LEGEND TREE (post-pruning)
--------------------------
{{#each legend.nodes}}
- id: {{this.layer_id}}
  display_name: "{{this.display_name}}"
  geometry_type: {{this.geometry_type}}
  visible: {{this.visible}}
  feature_count_in_extent: {{this.feature_count_in_extent}}
  parent_group: {{this.parent_group}}
  style_summary: "{{this.style_summary}}"
{{/each}}

OPTIONAL HINTS
--------------
brand_terminology: {{brand.glossary_json}}
```

---

## Output JSON Schema (abbreviated)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "LegendEdits",
  "type": "object",
  "additionalProperties": false,
  "required": ["edits", "diagnostics"],
  "properties": {
    "edits": {
      "type": "array",
      "items": {
        "oneOf": [
          {
            "type": "object", "additionalProperties": false,
            "required": ["op", "layer_id"],
            "properties": {
              "op": {"const": "hide"},
              "layer_id": {"type": "string"},
              "reason": {"type": "string", "maxLength": 160}
            }
          },
          {
            "type": "object", "additionalProperties": false,
            "required": ["op", "layer_id", "new_name"],
            "properties": {
              "op": {"const": "rename"},
              "layer_id": {"type": "string"},
              "new_name": {"type": "string", "maxLength": 60},
              "reason": {"type": "string", "maxLength": 160}
            }
          },
          {
            "type": "object", "additionalProperties": false,
            "required": ["op", "group_name", "members"],
            "properties": {
              "op": {"const": "group"},
              "group_name": {"type": "string", "maxLength": 40},
              "members": {
                "type": "array", "minItems": 2,
                "items": {"type": "string"}
              },
              "reason": {"type": "string", "maxLength": 160}
            }
          },
          {
            "type": "object", "additionalProperties": false,
            "required": ["op", "order"],
            "properties": {
              "op": {"const": "reorder"},
              "order": {
                "type": "array",
                "items": {"type": "string"}
              }
            }
          }
        ]
      }
    },
    "diagnostics": {
      "type": "object",
      "properties": {
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "notes": {"type": "string", "maxLength": 400}
      }
    }
  }
}
```

---

## Few-Shot Example

### Input

```
LEGEND TREE
- id: roads_primary, name "roads_primary", line, visible, 124 in extent, style "thick_red"
- id: roads_secondary, name "roads_secondary", line, visible, 312 in extent
- id: roads_tertiary, name "roads_tertiary", line, visible, 887 in extent
- id: flood_zone, name "flood_zone", polygon, visible, 42 in extent, style "hazard_blue"
- id: parcels, name "parcels", polygon, visible, 9412 in extent
- id: basemap, name "Esri World Imagery", raster, visible, ortho

AUDIENCE: government
LOCALE:   id-ID
```

### Output

```json
{
  "edits": [
    {
      "op": "group",
      "group_name": "Jaringan Jalan",
      "members": ["roads_primary", "roads_secondary", "roads_tertiary"],
      "reason": "3 layers share roads_* prefix and represent the same theme."
    },
    {
      "op": "rename",
      "layer_id": "flood_zone",
      "new_name": "Zona Rawan Banjir",
      "reason": "Translate to Indonesian for government audience."
    },
    {
      "op": "rename",
      "layer_id": "parcels",
      "new_name": "Persil Tanah",
      "reason": "Localized term."
    },
    {
      "op": "reorder",
      "order": [
        "Zona Rawan Banjir",
        "Jaringan Jalan",
        "Persil Tanah",
        "Esri World Imagery"
      ]
    }
  ],
  "diagnostics": {
    "confidence": 0.78,
    "notes": "Conservative grouping; basemap kept last."
  }
}
```

---

## Validation Notes

- Every `layer_id` referenced must exist in the input.
- The `reorder.order` array refers to **post-rename** names (or layer_ids if no rename applied).
- Group `members` must all exist; cannot be empty; cannot overlap across groups.
- All output is **proposed**; user confirms before applying.

---

## When NOT to call this prompt

- < 3 layers in the legend (no value).
- User has manually grouped/renamed (preserve manual edits).
- Audience is "academic" *and* density is "minimal" — usually flat is preferred there.

These conditions are checked in `application/query_ai_assistant.py` before issuing the call.
