# Experiment Template

Use this template for all Visual Lab experiments.

---

# Experiment ID

Example:

```text
TRACE_001_SHADOW
```

---

# Research Question

What single visual behavior is being studied?

Example:

```text
How does shadow preservation affect atmosphere and phone avoidance?
```

---

# Hypothesis

What do we expect to happen?

Example:

```text
Moderate shadow preservation with subtle texture will feel more believable than aggressive shadow lift or heavy crush.
```

---

# Variables

List variables being changed.

Example:

```text
- shadow depth
- contrast level
- noise amount
```

---

# Constants

List what should remain stable.

Example:

```text
- input images
- export dimensions
- processing order
```

---

# Dataset

Describe dataset sources.

Example:

```text
10 low-light iPhone images captured indoors and outdoors at night.
```

---

# Outputs

Describe generated outputs.

Example:

```text
- original
- phone_flat
- crush
- texture
- trace_candidate
- contact sheets
```

---

# Scoring Categories

Use the shared rubric.

Suggested categories:

- atmosphere
- believability
- shadow texture
- phone avoidance
- memory pressure

---

# Observations

Document:

- strongest behaviors
- weakest behaviors
- unexpected results
- recurring artifacts

---

# Conclusion

Summarize findings.

Example:

```text
Extreme shadow crush increased atmosphere but reduced believability.
The balanced TRACE candidate preserved more dimensionality while avoiding obvious HDR behavior.
```

---

# Next Experiment

Define the next isolated question.

Example:

```text
Study edge falloff and center weighting behavior.
```
