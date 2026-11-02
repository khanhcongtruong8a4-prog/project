# A2-Extended v4 complete handoff

Start with panda_research/reports/a2_extended_delivery/GATE_SUMMARY.md and
panda_research/reports/a2_extended_v4/A2_EXTENDED_RESULTS.md.

This ZIP contains ALL new code and evidence, including every failed v1/v2/v3
run, the clean original seven-cell reproduction and the complete v4 campaign.
The physical model and limits are unchanged. v4 explicitly changes the
velocity-CBF design gain 5→10; other gains/references/pass thresholds stay fixed.
Earlier failures are not relabeled. Source/policy/trace hashes are provided.

Full raw traces are losslessly encoded together in evidence/ to reduce download
size. They are NOT silently omitted. After extraction, reconstruct their exact
original files with the standard-library helper (no extra archive program):

    python archive_evidence.py restore --evidence evidence --destination . --report restored-proof.json

Every original CTZ byte SHA-256 is checked. A different existing file is never
overwritten. Exact reconstruction was verified on Python3.12.14/zlib1.3.2;
compatible compression versions are needed for identical outer CTZ bytes.
Original numeric arrays/schema bytes are stored losslessly without rounding.
Allow several GB of temporary disk space. Numerical replay uses the pinned
environment; do not infer safety/theorems from the archive format.

For a read-only mathematical audit after restoring and installing the pinned
research environment:

    cd panda_research
    python scripts/audit_saved_extended_v4.py --output /tmp/new-saved-v4-audit.json

There is no QP resolve or new motion in that audit. To rerun strict full source
freeze checks/motion, use the full source branch a2-extended-v4, which retains
the immutable original archived files. This ZIP supplies the complete NEW
overlay and unchanged runtime context, without duplicating all older archives
and Git history.

REVIEW.zip is an OPTIONAL small code/table/report subset for convenient review.
It explicitly omits raw payloads and cannot substitute for full reproduction.
The outer complete ZIP includes every encoded raw file, with reconstruction
proof and manifest. No independent reviewer identity/signature is fabricated.
Official A3 comparisons and Level 1 certification remain NO-GO.
