# Visual Lab Roadmap

Visual Lab should grow in measured phases. The goal is to build a durable research and experiment system, not a pile of disconnected scripts.

## Phase 1 — Lab scaffold

Status: started

Goals:
- create a dedicated lab workspace under `labs/visual_lab/`
- document operating principles
- define agent roles
- establish TRACE as the first project
- avoid modifying Hermes core runtime too early

Outputs:
- `README.md`
- `LAB.md`
- `AGENTS.md`
- `projects/trace/LAB.md`

## Phase 2 — TRACE Experiment 001 integration

Goals:
- place the TRACE Imaging Lab prototype inside the Visual Lab workspace
- preserve the standalone repo structure
- make Experiment 001: Shadow runnable from within the Hermes repository
- document input/output paths clearly

Target structure:

```text
labs/visual_lab/projects/trace/TRACE_LAB/
  data/
  src/
  experiments/
  docs/
  README.md
  requirements.txt
```

## Phase 3 — Visual scoring workflow

Goals:
- create a shared scoring rubric
- score outputs consistently across experiments
- separate technical scores from emotional/image-behavior scores
- generate repeatable review notes

Artifacts:
- `RUBRIC.md`
- experiment-specific CSV logs
- contact sheet notes
- reviewer observations

## Phase 4 — Dataset and reference archive

Goals:
- organize input images by source and rights tier
- keep originals untouched
- work only from copies
- classify reference images by behavior, not style

Possible folders:

```text
references/
  phone/
  disposable/
  early_digital/
  direct_flash/
  mixed_light/
  compression/
```

## Phase 5 — Hermes toolset integration

Goals:
- expose Visual Lab actions through Hermes tools or commands
- avoid deep core modifications until workflows are proven
- add a `visual_lab` or `trace_lab` toolset only after scripts stabilize

Possible future commands:

```bash
hermes visual list
hermes visual run trace exp_001_shadow
hermes visual score latest
hermes visual summarize latest
```

## Phase 6 — Agent-assisted experiment runner

Goals:
- let Hermes plan, run, and summarize experiments
- keep human review in the loop
- produce next-experiment recommendations
- maintain experiment lineage over time

Expected workflow:

1. user gives research question
2. agent creates experiment plan
3. script generates outputs
4. contact sheets are produced
5. agent summarizes findings
6. user scores outputs
7. next experiment is proposed

## Phase 7 — Roll coherence and camera identity

Goals:
- move beyond single-image transforms
- study consistency across a group of images
- define what makes a TRACE roll feel like one coherent memory object
- avoid obvious presets while preserving recognizable camera behavior

Research questions:
- How much variation should exist within a roll?
- Which traits should stay stable?
- Which traits should respond to scene conditions?
- When does consistency become a filter?
