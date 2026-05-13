# Visual Lab Dataset Guide

Datasets should be organized around image behavior, not aesthetics.

The purpose of the dataset system is to support controlled experiments.

---

# Dataset principles

## Preserve originals

Never modify source images.

Always:

- keep originals untouched
- work from copies
- preserve metadata when possible
- log dataset origins

---

## Organize by behavior

Prefer:

```text
mixed_light/
low_light/
direct_flash/
phone_hdr/
compression/
motion_softness/
```

Avoid:

```text
cool_photos/
vintage/
aesthetic/
retro/
```

---

# Recommended structure

```text
datasets/
  source/
    phone/
    disposable/
    early_digital/
    direct_flash/
    screenshots/
  working/
  exports/
  references/
```

---

# Dataset metadata

Each dataset should ideally include:

```text
source_device
lighting_conditions
time_of_day
movement_level
compression_history
notes
```

---

# Reference image categories

References should be tagged by observed behavior.

Examples:

- deep shadow retention
- mixed sodium lighting
- flash collapse
- dark clothing texture
- low-light blur
- edge falloff
- memory residue
- screenshot degradation

---

# Preferred source material

Strong source categories:

- old point-and-shoot cameras
- early CCD digital cameras
- disposable cameras
- nightlife flash photography
- low-light personal photos
- screenshots and repost chains
- compressed uploads
- accidental photos
- emotionally unplanned moments

---

# Avoid curated perfection

Avoid datasets dominated by:

- studio photography
- influencer imagery
- professional grading
- HDR-heavy edits
- highly curated lifestyle images

The lab studies believable capture behavior, not polished media production.
