# TRACE Imaging Lab V0

TRACE Imaging Lab is a small Python research prototype for testing image-processing ideas behind TRACE: a slim, screenless, daily-carry camera meant to preserve atmosphere instead of producing clean smartphone images.

TRACE is not a retro filter project. This lab avoids fake borders, fake dust, scratches, sprockets, VHS artifacts, and obvious presets. The goal is to study shadow, falloff, mixed light, texture, slight blur, roll coherence, and memory realism with restraint.

## Project structure

```text
TRACE_LAB/
  data/
    input/
      phone/
      reference/
    output/
      exp_001_shadow/
  src/
    ingest.py
    shadow.py
    texture.py
    export.py
    utils.py
  experiments/
    exp_001_shadow.py
  docs/
    experiment_log.md
    rubric.md
  README.md
  requirements.txt
```

## Setup

From the repo root:

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows PowerShell
pip install -r requirements.txt
```

## Add input images

Place casual phone images here:

```text
data/input/phone/
```

Supported formats:

- `.jpg`
- `.jpeg`
- `.png`
- `.tif`
- `.tiff`
- `.webp`

## Run Experiment 001: Shadow

From the repo root:

```bash
python experiments/exp_001_shadow.py
```

## Outputs

Experiment 001 saves results here:

```text
data/output/exp_001_shadow/
```

For each input image, the script generates:

1. `original` — unchanged baseline copy.
2. `phone_flat` — slightly lifted shadows, cleaner and more phone-like.
3. `crush` — deeper blacks and stronger contrast.
4. `texture` — deeper shadows plus subtle shadow texture.
5. `trace_candidate` — balanced TRACE-style shadow preservation.
6. A contact sheet comparing all five versions.
7. A CSV log named `exp_001_shadow_log.csv`.

## How to score results

Open each contact sheet and score every version using `docs/rubric.md`.

Score each image from 1–5 on:

1. Atmosphere
2. Believability
3. Shadow Texture
4. Phone Avoidance
5. Memory Pressure

The best TRACE result should not be the darkest or most stylized. It should preserve darkness while keeping the image believable. Blacks should feel physical, texture should remain subtle, and important subject detail should survive where possible.

## Design principles

- Preserve darkness; do not erase it.
- Avoid artificial crushed blacks.
- Avoid obvious grain.
- Avoid retro clichés.
- Preserve skin and important subject detail when possible.
- Prefer believable atmosphere over dramatic effect.
- Treat this as a lab, not a production imaging pipeline.
