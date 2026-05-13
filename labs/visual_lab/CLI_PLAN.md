# Visual Lab CLI Plan

The Visual Lab CLI layer should remain lightweight.

The goal is orchestration and reproducibility, not a giant framework.

---

# Philosophy

The CLI should:

- launch experiments
- organize outputs
- create contact sheets
- log runs
- summarize experiments
- keep structure predictable

The CLI should NOT:

- hide image behavior behind abstractions
- become a complex app framework
- replace direct experiment inspection

---

# Proposed command structure

## List labs

```bash
hermes visual list
```

Returns:

```text
trace
deadflash
texture_science
```

---

## List experiments

```bash
hermes visual experiments trace
```

Returns:

```text
001_shadow
002_falloff
003_mixed_light
```

---

## Run experiment

```bash
hermes visual run trace 001_shadow
```

Actions:

1. load dataset
2. create timestamped run folder
3. execute experiment script
4. export outputs
5. create contact sheets
6. generate log files

---

## Review latest run

```bash
hermes visual review latest
```

Should:

- open output folder
- display contact sheet paths
- summarize generated metadata

---

## Generate summary

```bash
hermes visual summarize latest
```

Should produce:

- observations
- strongest outputs
- weakest outputs
- possible next experiments

---

# Output conventions

Every run should generate:

```text
runs/
  2026-05-13_001_shadow/
    outputs/
    contact_sheets/
    logs/
    summary.md
```

---

# Design principle

Visual Lab commands should feel:

- inspectable
- scriptable
- modular
- minimal
- reproducible

The CLI is an experiment launcher, not a black box.
