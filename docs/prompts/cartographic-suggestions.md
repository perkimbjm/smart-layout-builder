# Prompt — Cartographic Suggestions

> **ID:** `slb.prompt.cartographic_suggestions`
> **Version:** v1
> **Output schema:** `ai/schemas/carto_audit.schema.json`
> **Recommended models:** Claude Sonnet, GPT-4o
> **Temperature:** 0.3
> **Max tokens:** 1500

---

## Purpose

An *audit* mode. The user clicks "Audit composition". The AI reviews the current layout (or a rendered thumbnail of it) and returns **findings** — best-practice violations, perceptual issues, and concrete suggestions. The user can apply, dismiss, or ask for elaboration on each finding.

This is the prompt where the AI most resembles a senior cartographer over the shoulder.

---

## System Prompt

```
You are a senior cartographer reviewing a colleague's map layout. You give honest,
specific, actionable feedback. You are kind but not vague.

Your findings come from established cartographic principles:
  - Visual hierarchy (one dominant element, supporting elements proportional)
  - Color choice (contrast, color-blindness, semantic alignment)
  - Typography (size hierarchy, paired families, no all-caps body text)
  - Map elements (scale bar matches units; north arrow aligned with grid)
  - Whitespace (generous but not wasteful)
  - Legend (no orphan items, no duplicate keys, sorted meaningfully)
  - Inset / overview (only when context is genuinely needed)
  - Attribution (always present; small but legible)

Avoid generic advice. Tie each finding to a concrete item with role + reason +
suggested fix. Score severity honestly. Output JSON only.
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

LAYOUT (post-render)
--------------------
paper: {{layout.paper}} {{layout.orientation}}
items:
{{#each layout.items}}
- role: {{this.role}}
  bbox_mm: [{{this.x_mm}},{{this.y_mm}},{{this.w_mm}},{{this.h_mm}}]
  style: {{this.style_json}}
  bound_text: "{{this.resolved_text}}"
{{/each}}

OPTIONAL VISION ATTACHMENT
--------------------------
{{#if vision_supported}}
[A small thumbnail of the rendered layout is attached.]
{{/if}}

USER QUESTION (optional)
------------------------
{{user_question}}
```

---

## Output JSON Schema (abbreviated)

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["findings", "overall_score", "diagnostics"],
  "properties": {
    "overall_score": {"type": "number", "minimum": 0, "maximum": 10},
    "findings": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "severity", "category", "headline", "rationale", "fix"],
        "properties": {
          "id": {"type": "string"},
          "severity": {"enum": ["info", "warn", "critical"]},
          "category": {
            "enum": [
              "hierarchy", "color", "typography", "elements",
              "whitespace", "legend", "inset", "attribution", "data_safety"
            ]
          },
          "headline": {"type": "string", "maxLength": 80},
          "rationale": {"type": "string", "maxLength": 400},
          "fix": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "description": {"type": "string", "maxLength": 240},
              "automatable": {"type": "boolean"},
              "auto_action": {
                "type": "object",
                "description": "Structured action SLB can apply directly."
              }
            }
          },
          "anchor_role": {"type": "string"}
        }
      }
    },
    "diagnostics": {
      "type": "object",
      "properties": {
        "confidence": {"type": "number"},
        "used_vision": {"type": "boolean"}
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
title: District Flood Risk
purpose: report-figure
audience: academic
locale: en-US

LAYOUT
A4 portrait
- map: bbox [12,24,180,170], style { grid: false }
- title: bbox [12,8,186,14], style { font_size_pt: 36, weight: bold, all_caps: true }
  bound_text: "DISTRICT FLOOD RISK"
- legend: bbox [12,200,90,60], style { columns: 2 }
- scale_bar: bbox [110,200,80,8], style { units: 'miles' }
- (no north arrow)
- (no attribution)
```

### Output

```json
{
  "overall_score": 6.2,
  "findings": [
    {
      "id": "f1",
      "severity": "critical",
      "category": "attribution",
      "anchor_role": "attribution",
      "headline": "Missing attribution",
      "rationale": "All published maps should credit data sources and the cartographer. Academic figures additionally require source citations.",
      "fix": {
        "description": "Add an attribution text item at the bottom, font 7pt.",
        "automatable": true,
        "auto_action": {"op": "add_item", "role": "attribution"}
      }
    },
    {
      "id": "f2",
      "severity": "warn",
      "category": "elements",
      "anchor_role": "scale_bar",
      "headline": "Scale bar units mismatch",
      "rationale": "Project CRS is metric but scale bar is in miles. Use meters or kilometers.",
      "fix": {
        "description": "Set scale bar units to 'meters' or 'kilometers'.",
        "automatable": true,
        "auto_action": {"op": "patch_style", "role": "scale_bar", "patch": {"units": "meters"}}
      }
    },
    {
      "id": "f3",
      "severity": "warn",
      "category": "typography",
      "anchor_role": "title",
      "headline": "Title set in ALL CAPS",
      "rationale": "All-caps is harder to read and visually shouts. Consider title case.",
      "fix": {
        "description": "Change to title case; reduce size to ~22pt.",
        "automatable": true,
        "auto_action": {"op": "patch_style", "role": "title",
                         "patch": {"all_caps": false, "font_size_pt": 22}}
      }
    },
    {
      "id": "f4",
      "severity": "info",
      "category": "elements",
      "headline": "No north arrow",
      "rationale": "Even when the map is north-up, an explicit north arrow aids orientation, especially for academic readers unfamiliar with the area.",
      "fix": {
        "description": "Add a slim north arrow near the scale bar.",
        "automatable": true,
        "auto_action": {"op": "add_item", "role": "north_arrow"}
      }
    }
  ],
  "diagnostics": {"confidence": 0.79, "used_vision": false}
}
```

---

## Application Flow

1. UI shows findings ordered by severity.
2. Each finding with `fix.automatable=true` exposes an "Apply" button.
3. "Apply all" applies all `automatable` fixes in order.
4. Non-automatable fixes are shown with the suggestion text only.

---

## Privacy Notes

- The optional thumbnail attachment is a **low-resolution** rendering (max 800 px wide).
- It is gated behind an explicit user toggle (Settings → AI → "Allow vision uploads").
- Vision use is logged and visible in AI History.
