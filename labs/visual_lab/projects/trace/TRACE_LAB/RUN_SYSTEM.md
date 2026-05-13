# TRACE Run System

The run system exists to preserve experiment lineage.

Every experiment execution should become a reviewable historical artifact.

The goal is not simply generating outputs.
The goal is building visual research continuity over time.

---

# Why runs matter

Without structured runs:

- experiments become difficult to compare
- parameter changes become hard to track
- successful behaviors get lost
- regressions become invisible
- emotional evaluation becomes inconsistent

TRACE should evolve through accumulated comparison.

---

# Proposed structure

```text
runs/
  2026-05-13_trace_001_shadow_v1/
    outputs/
    contact_sheets/
    logs/
    manifest.json
    summary.md
```

---

# Required run artifacts

## 1. Outputs

All generated versions.

Example:

```text
bar_night_trace_candidate.jpg
```

---

## 2. Contact sheets

Primary review surface.

Should allow:

- side-by-side comparison
- emotional evaluation
- rapid visual scanning

---

## 3. Manifest

Stores:

- experiment id
- timestamp
- parameters
- dataset used
- output versions
- processing values

Example:

```json
{
  "experiment": "TRACE_001_SHADOW",
  "dataset": "low_light_v1",
  "crush_strength": 0.12,
  "noise_level": 0.015
}
```

---

## 4. Summary

Human-readable observations.

Should describe:

- strongest outputs
- weakest outputs
- recurring artifacts
- emotional observations
- next experiment ideas

---

# Future evolution

Later versions of the run system may include:

- automated summaries
- experiment clustering
- historical comparisons
- parameter heatmaps
- roll coherence analysis
- visual behavior indexing

---

# Design principle

The run system should feel:

- inspectable
- archival
- reproducible
- human-readable
- emotionally evaluative

Not opaque or over-automated.
