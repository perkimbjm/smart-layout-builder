# Prompt — Adaptive Positioning

> **ID:** `slb.prompt.adaptive_positioning`
> **Version:** v1
> **Output schema:** `ai/schemas/positioning_plan.schema.json`
> **Recommended models:** GPT-4o, Claude Sonnet
> **Temperature:** 0.15
> **Max tokens:** 1200

---

## Purpose

A layout exists. Something changed (paper resized, orientation flipped, a layer was added/removed, the user moved an item manually). The deterministic `ConstraintSolver` has produced a candidate re-flow, but **wants a sanity check** on whether the result is visually balanced and cartographically sound.

This prompt either:
- Approves the candidate (`approved: true`, possibly with minor `nudges`).
- Proposes an alternative repositioning.

It runs **after** the solver, never replacing it.

---

## System Prompt

```
You are a quality reviewer for cartographic layouts. You receive:
  - The previous layout state.
  - The current layout state (post-resize / post-change).
  - The constraint solver's diagnostics.

You decide if the current state is acceptable. If yes, return approved=true and
optionally suggest small nudges (≤ 5mm). If no, return approved=false and supply
a corrected positioning plan.

Hard constraints (any violation → not approved):
  - No item overlaps another by more than 1mm.
  - No item escapes paper bounds (incl. safe_margin).
  - Map item remains the dominant element (largest area).
  - Title is at the top edge band.
  - Scale bar and north arrow are not adjacent to each other (visual confusion).

Soft constraints (prefer to honor):
  - Legend stays on the same side of the map across resizes when possible.
  - Aspect ratios of paper and map should track (within ±15%).
  - Whitespace distribution is roughly balanced.

Output JSON only.
```

---

## User Prompt Template

```
PREVIOUS STATE
--------------
paper: {{prev.paper}}
orientation: {{prev.orientation}}
items: {{prev.items_json}}        # role, x, y, w, h

CURRENT STATE (post-solver)
---------------------------
paper: {{curr.paper}}
orientation: {{curr.orientation}}
items: {{curr.items_json}}

SOLVER DIAGNOSTICS
------------------
iterations: {{solver.iterations}}
unsatisfied: {{solver.unsatisfied_json}}
move_distance_mm_total: {{solver.move_distance_mm_total}}

CHANGE THAT TRIGGERED THE REFLOW
--------------------------------
type: {{change.type}}              # resize | orientation_flip | layer_added | layer_removed | manual_move
detail: {{change.detail_json}}
```

---

## Output JSON Schema (abbreviated)

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["approved", "diagnostics"],
  "properties": {
    "approved": {"type": "boolean"},
    "nudges": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["role", "dx_mm", "dy_mm"],
        "additionalProperties": false,
        "properties": {
          "role": {"type": "string"},
          "dx_mm": {"type": "number", "minimum": -5, "maximum": 5},
          "dy_mm": {"type": "number", "minimum": -5, "maximum": 5},
          "reason": {"type": "string", "maxLength": 120}
        }
      }
    },
    "alternative_layout": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["role", "x_mm", "y_mm", "w_mm", "h_mm"],
        "properties": {
          "role": {"type": "string"},
          "x_mm": {"type": "number"},
          "y_mm": {"type": "number"},
          "w_mm": {"type": "number", "exclusiveMinimum": 0},
          "h_mm": {"type": "number", "exclusiveMinimum": 0}
        }
      }
    },
    "diagnostics": {
      "type": "object",
      "properties": {
        "rule_violations": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1}
      }
    }
  }
}
```

---

## Decision Logic (consumer side)

```python
proposal = ai.complete(req)
if proposal.parsed_json["approved"]:
    apply_nudges(proposal.parsed_json.get("nudges", []))
else:
    if "alternative_layout" in proposal.parsed_json:
        # Run alternative through ConstraintSolver one more time before applying.
        cleaned = solver.validate(proposal.parsed_json["alternative_layout"])
        apply(cleaned)
    else:
        # AI rejected but had no alternative — keep current state, surface a banner.
        ui.warn("AI flagged the layout but proposed no alternative.")
```

---

## Few-Shot Example

### Input (resize A4 → A3, items just stretched)

```
PREV: A4 portrait — map 12,24,186,210; legend 12,240,186,45
CURR: A3 portrait — map 17,34,263,297; legend 17,338,263,63
solver.unsatisfied: ["aspect_ratio(map): 0.88 vs paper 0.70"]
```

### Output

```json
{
  "approved": false,
  "alternative_layout": [
    {"role": "map", "x_mm": 17, "y_mm": 34, "w_mm": 195, "h_mm": 280},
    {"role": "legend", "x_mm": 220, "y_mm": 34, "w_mm": 80, "h_mm": 200},
    {"role": "scale_bar", "x_mm": 220, "y_mm": 240, "w_mm": 80, "h_mm": 10},
    {"role": "north_arrow", "x_mm": 280, "y_mm": 255, "w_mm": 20, "h_mm": 20}
  ],
  "diagnostics": {
    "rule_violations": [
      "map aspect drifted >15% from paper aspect after naive stretch"
    ],
    "confidence": 0.81
  }
}
```

---

## Failure & Fallback

- If the AI cannot decide, it must return `approved: true` (conservative). The solver's output stands.
- If JSON invalid: solver output stands.
- Token budget: this prompt is small enough to be cheap; cache by `hash(prev + curr + change)`.
