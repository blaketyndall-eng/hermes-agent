"""Retrospective helpers for TRACE Imaging Lab.

These utilities help transform experiment runs into interpretable research
artifacts instead of disposable outputs.
"""

from pathlib import Path


def create_run_retrospective(
    run_dir: str | Path,
    experiment_id: str,
    profile_name: str = "default",
) -> Path:
    """Generate a starter retrospective markdown document for a run."""
    run_dir = Path(run_dir)
    retrospective_path = run_dir / "retrospective.md"

    content = f"""# TRACE Run Retrospective

Run Directory:
{run_dir.name}

Experiment ID:
{experiment_id}

Profile:
{profile_name}

---

# Initial Behavioral Notes

_To be filled after review._

## Strongest atmosphere

## Strongest anti-phone behavior

## Most believable shadow behavior

## Most emotionally memorable image

---

# Failures

Document:

- muddy blacks
- over-clean shadows
- fake texture
- stylized contrast
- unrealistic instability

---

# Primitive Observations

## darkness_confidence

## shadow_texture

## environmental_ambiguity

## motion_softness

## foreground_pressure

---

# Sequence Notes

Did the outputs feel coherent together?

Did any outputs feel repetitive or overly uniform?

---

# Next Research Direction

Suggested next experiment:

Reason:
"""

    retrospective_path.write_text(content, encoding="utf-8")
    return retrospective_path
