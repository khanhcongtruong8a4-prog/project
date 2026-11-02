# Exact replay and standalone ZIP reproduction

The verification predeclaration was committed before the fresh 19-cell motion
replay. Original model, controllers, policies, references, thresholds, clocks
and integration source files were not edited. Original unchanged CLI runners
executed every new P1 and motion; no old trajectory was substituted for a run.
Commands, stdout/stderr, package/platform inventory, source hashes and exit
codes are in the replay directory.

Exact comparison covers all state, observer, reference, controller, QP matrix,
dual/solver-result, slack, stage/endpoint, energy and metric data retained in
the P1/execution traces. Only solve_runtime_s is removed as nondeterministic
instrumentation; no physical value gets a new tolerance. Refinement uses the
original unchanged inequalities separately. Metadata paths, timestamps and
outer archive compression timestamps are not simulated physical data.

Use Python3.12.14 on the recorded Linux environment and the unmodified pinned
requirements plus setuptools80.9.0. Exact bytes of compressed containers were
verified using zlib1.3.2. A differing compression runtime must not be silently
treated as identical evidence. The supplied dependency lock pins versions;
it is not a distribution-hashed lock.

The complete ZIP includes every old protected input and failed experiment,
not only the earlier overlay. Its restore tools reconstruct original bytes
and refuse different existing files. RUN_REPRODUCTION.py restores inputs,
then the original runners' full pre-motion SHA checks execute. A ZIP without
Git metadata gets a clearly labeled LOCAL input-staging commit solely to run
those unchanged checks. This is not a fabricated historical commit, signature
or independent machine reproduction. In a full Git checkout no such staging
is needed. The historical source/control commit IDs remain separately recorded.

The standalone restore/bootstrap/frozen-input checks and archive integrity are
verified during delivery. The fresh physical replays were executed in a clean
Git checkout; their data are included rather than claiming a second unrun
physical execution from the final downloaded ZIP.
