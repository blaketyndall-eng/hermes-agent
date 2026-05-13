# TRACE Roll-Aware Execution

Roll-aware execution means images are processed as part of a sequence.

A roll is not a batch folder.

A roll is a coherent emotional object.

---

# Core Principle

Each image should adapt to its own scene.

But the sequence should preserve shared behavioral tendencies.

This creates:

```text
coherence without uniformity
```

---

# What Should Persist Across a Roll

Examples:

- darkness confidence
- shadow texture restraint
- motion softness tendency
- environmental ambiguity
- phone avoidance
- memory pressure

---

# What Should Drift

Examples:

- exposure pressure
- texture intensity
- falloff strength
- contrast behavior
- environmental color ambiguity

Drift should be subtle.

It should feel like lived capture variation, not random parameter noise.

---

# What Should Never Happen

Avoid:

- identical processing on every image
- random variation with no sequence logic
- obvious preset repetition
- aggressive artificial drift
- fake roll aging

---

# Roll-Aware Execution Model

```text
roll manifest
→ profile
→ base behavior parameters
→ controlled drift curve
→ image-level adaptation
→ roll evaluation
```

---

# Early Implementation Strategy

Start simple:

1. Load a roll manifest.
2. Load its behavior profile.
3. Calculate per-image drift values.
4. Apply subtle parameter offsets.
5. Save all outputs into a roll run folder.
6. Evaluate sequence coherence.

---

# Controlled Drift Example

For a 24-image roll:

```text
image 01: darkness +0.00
image 06: darkness +0.01
image 12: darkness -0.01
image 18: darkness +0.02
image 24: darkness +0.00
```

This should feel nearly invisible.

The point is not style variation.
The point is preventing mechanical sameness.

---

# Key Question

Does the roll feel like one remembered experience?

Not:

Do all images look the same?
