# Verified downloads and reproduction

The small ZIP is **6.4 MiB** (6,684,465 bytes). It contains runnable source,
reports and all nine mathematical/clock tests plus the 39-fixture T27 replay.
It omits raw payloads. The full evidence ZIP is **375.0 MiB** (393,215,409 bytes)
and contains all new raw evidence and linked historical annex provenance.
Both actual URLs returned HTTP200 and passed ZIP CRC and SHA256 checks.

- [Small runnable ZIP](https://raw.githubusercontent.com/khanhcongtruong8a4-prog/project/05419d457ee23d88e32439d898015bfb27a59ae2/ACTIVE_FILTER_REPRODUCTION.zip)
- [Complete evidence ZIP](https://github.com/khanhcongtruong8a4-prog/project/archive/05419d457ee23d88e32439d898015bfb27a59ae2.zip)
- [Evidence in parts of at most20 MiB](https://github.com/khanhcongtruong8a4-prog/project/blob/05419d457ee23d88e32439d898015bfb27a59ae2/EVIDENCE_PARTS.md)

To avoid one large download, extract the small ZIP and run from its root:

    python panda_research/scripts/fetch_active_sd_evidence.py --base-url https://raw.githubusercontent.com/khanhcongtruong8a4-prog/project/05419d457ee23d88e32439d898015bfb27a59ae2
    python RUN_ACTIVE_FILTER.py --restore --verify-only

The first command checks every part against its manifest, supports resuming
interrupted downloads, and preserves changed existing files. The second checks
all101 exact restored CTZ/gzip/NPZ bytes. Use recorded Python3.12.14 and pinned
dependencies as described in README_ACTIVE_FILTER.md.

The cleanly extracted small package passed all9 tests and all39 T27 fixtures.
The complete package restored all101 encoded files, and all589 logical files
matched source SHA256. Its fresh read-only trace analysis reproduced all8 cell
scientific JSON records, all20 operator/alignment NPZ archives, and the complete
modified-equation JSON/NPZ exactly; only measured analysis wall times differ.
No new external verifier or human signature is claimed. Every gate remains
as stated in ACTIVE_FILTER_GATE_DECISION.md; failed refinement is still failed.

Small ZIP SHA256: `006c387c9d0d5aa90ccf949c810e4d12f9717bdfa9be3f6107579c6986aa7dc8`

Full ZIP SHA256: `40ea7d9c9b64813cf90030f2bbf2617d41344358bdf36caece2cb80733352273`

The immutable artifact predates this download proof by necessity. This source
commit adds delivery validation without changing its scientific source154d8fa,
original data, thresholds, controller or published package bytes.
