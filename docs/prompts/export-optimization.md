# Prompt — Export Optimization

> **ID:** `slb.prompt.export_optimization`
> **Version:** v1
> **Output schema:** `ai/schemas/export_plan.schema.json`
> **Recommended models:** GPT-4o-mini, Claude Haiku (this is mostly heuristic; keep cheap)
> **Temperature:** 0.1
> **Max tokens:** 600

---

## Purpose

Given the parameters of an upcoming atlas export — coverage size, feature complexity, output format, target machine — propose an **execution plan**:

- Number of parallel workers.
- DPI policy (uniform vs adaptive).
- Memory ceiling per worker.
- Chunk size (features per worker batch).
- Whether to enable resume.
- Whether to inline rasters or reference them.
- Whether to merge into a single PDF or keep separate files.

The Atlas Orchestrator already has deterministic defaults. This prompt **refines** them based on the actual workload.

---

## System Prompt

```
You are an optimization advisor for QGIS batch atlas exports. You take a workload
description and a machine description and return a single JSON execution plan.

Goals (in priority order):
  1. Reliability — never propose a plan that may OOM the machine.
  2. Throughput — minimize wall-clock time within the memory budget.
  3. Quality — only reduce DPI when bandwidth/memory force it; otherwise honor user DPI.

Heuristics you may use:
  - workers ≤ cpu_cores, but cap at 8 unless ram_per_worker > 1.5 GB.
  - chunk_size larger when each render is fast (< 2s), smaller when slow.
  - Disable single-PDF merge if total page count > 2000 and RAM < 16 GB.
  - For raster-heavy workloads, prefer lower workers with larger memory.
  - For vector-only workloads, push workers up to CPU count.

Output JSON only. Include a rationale string ≤ 200 chars.
```

---

## User Prompt Template

```
WORKLOAD
--------
features_total: {{workload.features_total}}
avg_render_seconds_est: {{workload.avg_render_seconds_est}}
output_format: {{workload.output_format}}      # pdf | png | svg | geopdf
target_dpi: {{workload.target_dpi}}
single_merged_pdf: {{workload.single_merged_pdf}}
raster_heavy: {{workload.raster_heavy}}        # bool
total_raster_size_mb_est: {{workload.total_raster_size_mb_est}}
layout_complexity: {{workload.layout_complexity}}   # low | medium | high

MACHINE
-------
cpu_cores_logical: {{machine.cpu_cores_logical}}
cpu_cores_physical: {{machine.cpu_cores_physical}}
ram_total_gb: {{machine.ram_total_gb}}
ram_available_gb: {{machine.ram_available_gb}}
disk_free_gb: {{machine.disk_free_gb}}
on_battery: {{machine.on_battery}}              # bool — throttle when true

USER PREFERENCES
----------------
priority: {{prefs.priority}}                    # speed | quality | balanced
allow_dpi_reduction: {{prefs.allow_dpi_reduction}}
```

---

## Output JSON Schema (abbreviated)

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["workers", "chunk_size", "memory_ceiling_mb_per_worker",
               "dpi", "enable_resume", "single_merged_pdf", "rationale"],
  "properties": {
    "workers": {"type": "integer", "minimum": 1, "maximum": 32},
    "chunk_size": {"type": "integer", "minimum": 1, "maximum": 200},
    "memory_ceiling_mb_per_worker": {"type": "integer", "minimum": 256},
    "dpi": {"type": "integer", "minimum": 72, "maximum": 600},
    "enable_resume": {"type": "boolean"},
    "single_merged_pdf": {"type": "boolean"},
    "inline_rasters": {"type": "boolean"},
    "estimated_wall_seconds": {"type": "number"},
    "estimated_peak_ram_gb": {"type": "number"},
    "rationale": {"type": "string", "maxLength": 200},
    "warnings": {"type": "array", "items": {"type": "string"}}
  }
}
```

---

## Few-Shot Examples

### Example 1 — small vector workload, fast machine

**Input**:
- features_total: 56, avg_render_seconds_est: 1.4, format: pdf, dpi: 300, raster_heavy: false, complexity: low
- machine: 8 cores logical / 4 physical, 16 GB RAM (10 free), on_battery: false
- prefs: speed

**Output**:
```json
{
  "workers": 8,
  "chunk_size": 7,
  "memory_ceiling_mb_per_worker": 1024,
  "dpi": 300,
  "enable_resume": true,
  "single_merged_pdf": true,
  "inline_rasters": true,
  "estimated_wall_seconds": 12,
  "estimated_peak_ram_gb": 6,
  "rationale": "Vector-only, fast machine — push to 8 workers; chunk by 7 evenly across workers.",
  "warnings": []
}
```

### Example 2 — large raster workload, modest machine

**Input**:
- features_total: 1200, avg_render_seconds_est: 6.8, format: pdf, dpi: 300, raster_heavy: true, raster_size_mb: 3500, complexity: high
- machine: 8 cores logical / 4 physical, 16 GB RAM (8 free), on_battery: true
- prefs: balanced

**Output**:
```json
{
  "workers": 3,
  "chunk_size": 8,
  "memory_ceiling_mb_per_worker": 2200,
  "dpi": 250,
  "enable_resume": true,
  "single_merged_pdf": false,
  "inline_rasters": false,
  "estimated_wall_seconds": 2730,
  "estimated_peak_ram_gb": 7.2,
  "rationale": "Raster-heavy; on battery — limit workers to 3; skip merged PDF to control peak RAM; mild DPI drop with user consent.",
  "warnings": [
    "Reduced DPI 300→250 to fit memory; disable allow_dpi_reduction to override.",
    "Skipping single-merged PDF due to total page count + RAM constraints."
  ]
}
```

---

## Consumer Logic

```python
plan = ai.complete(req).parsed_json

# Validate against absolute caps
plan["workers"] = min(plan["workers"], machine.cpu_cores_logical)
plan["dpi"] = plan["dpi"] if prefs.allow_dpi_reduction else workload.target_dpi

# Apply
orchestrator.run(
    workers=plan["workers"],
    chunk_size=plan["chunk_size"],
    memory_ceiling=plan["memory_ceiling_mb_per_worker"],
    dpi=plan["dpi"],
    resume=plan["enable_resume"],
    single_merge=plan["single_merged_pdf"],
)

# Surface warnings in UI
for w in plan.get("warnings", []):
    ui.warn(w)
```

---

## When NOT to call

- features_total < 10 → defaults are fine.
- Same workload was planned in the last 24h → use cache.
- AI is disabled → use built-in heuristic in `ExportService._default_plan()`.

---

## Validation & Safety

- Schema enforces bounds (workers ≤ 32, dpi ∈ [72, 600]).
- Consumer applies absolute caps from settings before honoring the plan.
- Estimated peak RAM is informational only — never trusted as a safety bound (we still enforce ceilings per worker).
