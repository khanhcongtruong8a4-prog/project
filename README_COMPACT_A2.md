# Small A2 download

Download **IC2AI_Panda_A2_v2.4b_RUNTIME.zip — 23.5 MB** directly from downloads/.
The repository-wide Download ZIP still includes the multi-GB historical evidence.

The small package contains source, normative inputs, tested native libraries,
mathematical notes, result summaries, and the fixtures required by its tests.
The controller/integrator/QP mathematics and thresholds are unchanged. Bulk
history is preserved separately at immutable scientific commit c1d0fd2.

Validation: clean Python 3.12.14 virtual environment containing only five pinned
runtime dependencies; all 104 tests passed; one complete alpha10 active cell
freshly simulated and independently audited. Both candidate plans match the
qualified source, and the numerical execution function bytecode is identical.
All 27 physical cells were not rerun merely for repackaging.

Inside the ZIP, follow README_COMPACT.md. Default RUN_COMPACT_A2.py executes the
104 tests; --candidate alpha10 --cell 0 runs a full fresh active cell; --all
regenerates the 7 + 12 + 8 numerical cells and refinements. Generated traces use
local disk space. No multi-GB download is required for these compact commands.
The old archive-byte integrity gate is explicitly NOT RUN when its payloads
are omitted. It is never marked as passed. No new A3 or Level1 claim is made.
