# Clean engineering reproduction — passed

A new Python 3.12 virtualenv was populated from the pinned requirements and the
project installed into a fresh extracted baseline plus remediation overlay.
The original working virtualenv and installed source paths were not used.
This is a separate virtualenv/file tree on the same host, run by the engineering
assistant; it is not an independent human review or a different-machine claim.

Results: 13 signed-clock/hold contract tests PASS; 15 existing static-screen
tests PASS; 19 Action 3 component tests PASS; independent-reference T28 PASS;
source/Pinocchio/MuJoCo and original-model regressions PASS; dependency check PASS.
The A2 entry command correctly refuses execution.

The frozen Panda hold reproduces FAIL in all four C4 preparation cells, with
joints 3 and 7 outside the unchanged speed window at elapsed 1.25 ms. Its exit
code 3 is the expected scientific rejection. The evidence-aware A2 checker
returns exit 1 for that failed startup and official A2 remains NO-GO.

Fresh and working controller/test source hashes match. Installer tests cover a
fresh r2 baseline, upgrading accepted P1 r1, idempotence and rejection of local
edits before any write. Exact commands, environment packages, outputs and source
hashes are in [the record](evidence/clean_engineering/clean_reproduction.json).

The final ZIP adds these reports and checksum bookkeeping after testing; its
controller/test source is unchanged. Human controls/theory signatures, build
confirmation and written A2 authorization remain pending.
