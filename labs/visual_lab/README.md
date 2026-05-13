# Visual Lab

Visual Lab is a project workspace inside Hermes Agent for image-behavior research, experiment orchestration, and creative technical development.

It is intentionally separated from the Hermes core runtime. The goal is to use Hermes as the agent operating layer while keeping research projects, lab notes, prompts, and experiments in a clean workspace.

## Purpose

Visual Lab studies visual behavior rather than surface style.

It is built for projects like:

- TRACE Imaging Lab
- DEADFLASH texture research
- camera behavior studies
- old digital / disposable / phone comparison work
- visual taxonomy building
- experiment logging
- contact sheet review workflows

## Core principle

Do not build obvious filters.

Study what images do:

- shadow
- falloff
- mixed light
- texture
- blur
- compression
- sensor limits
- atmosphere
- memory realism

## Workspace structure

```text
labs/visual_lab/
  README.md
  LAB.md
  AGENTS.md
  RUBRIC.md
  projects/
    trace/
      LAB.md
      experiments/
      datasets/
      outputs/
    deadflash/
      LAB.md
      research/
      datasets/
      outputs/
  runs/
  notes/
```

## Operating mode

Visual Lab should favor small experiments, clear logs, and comparison sheets over big speculative builds.

Every experiment should answer one question.

Every output should be reviewable.

Every conclusion should lead to the next experiment.
