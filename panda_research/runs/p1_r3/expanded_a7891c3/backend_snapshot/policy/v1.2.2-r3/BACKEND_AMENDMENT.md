# Geometry execution backend amendment — no controller retuning

After freeze `51831ee`, all 12 r3 engineering contracts passed. The first
full-model command used the original interpreted MX flange derivatives.
Measured geometry evaluation cost was 0.17–0.21 seconds per call, making the
five-stage diagnostics for the four full horizons unnecessarily expensive.
The initial command was interrupted for this engineering reason before any
completed prehold, zero endpoint or A2 result. Its partial run, log and
interruption note are retained; it is not counted as a scientific rejection or
a completed test. CasADi translated SIGINT into a DM_full exception, after
which SIGTERM ended the command. Do not treat that exception as a model result.

The controller, gains, plan, RK4 algorithm, observer, QP, acceptance thresholds
and all original frozen files remain byte-identical to `51831ee`. The amendment
only evaluates the original CasADi geometry function through `Function.expand()`:
the same expression expanded to scalar SX operations. The original
`FlangeGeometry` source and the approved dynamics evaluator are not changed.
The separate launch wrapper selects this backend for all four cells.

Commit `BACKEND_FROZEN_INPUTS.json` before this launch. Before any plant cell,
the wrapper must compare all five outputs (flange, translational Jacobian,
W, gradient W and Hessian W) against the original function at all 154 retained
regression configurations, requiring **bitwise equality**, with no tolerance.
Abort rather than use a different threshold if any comparison fails. Record
the full pose list, per-output differences and both backend runtimes. Equality
at these configurations is engineering regression evidence, not a global
roundoff bound or independent validation. The mathematical expression graph
remains the same for all subsequent stage states.

The original frozen runner still verifies every original input and controls
all numerical semantics, logging and acceptance. The wrapper records a second
freeze commit and its own source snapshot alongside the original run metadata.
No candidate is selected by a trial result and no scalar is retuned.

```bash
cd /workspace/project/panda_research
/workspace/panda-venv/bin/python scripts/p1_r3_expanded.py
```

This is the practical reproduction command for the complete four-cell run.
The original command remains available as a slower expression-equivalent path.
