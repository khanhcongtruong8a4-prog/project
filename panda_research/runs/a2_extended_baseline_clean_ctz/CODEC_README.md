# Lossless archival copy of the clean baseline reproduction

The original fresh 7-cell run remains unchanged at the source path recorded in
TRANSCODE_INDEX.json. This directory includes all its nontrace metadata/source
snapshots and all 14 raw trace streams in CTZ format. CTZ preserves every native
JSON value, float64 bit (including signed zero), scalar type, key order and
ragged list; it does not quantize or pickle. The unit suite includes the full
baseline cell-0 trace and corruption rejection.

All 14 streams were decoded after writing. Their original JSON bytes and original
gzip bytes were reconstructed exactly, verified by SHA-256, with Python3.12.14
and zlib1.3.2. The original gzip inputs were checked unchanged. The exact raw-JSON
restoration is portable; reproducing identical gzip container bytes additionally
requires a compatible gzip encoder. Separate original gzip/raw JSON hashes and
CTZ checksums are in TRANSCODE_INDEX.json.

The source gzip streams total 84,196,147 bytes. CTZ streams total 67,126,256 bytes.
This is a lossless packaging change, not a new numerical experiment or a change
to acceptance criteria. Original baseline metadata retains the original gzip
filenames and hashes. Decode before using readers that expect those originals.

From an archive with this directory under panda_research/runs/ and the included
codec under panda_research/src/:

```bash
python restore_json.py --output /tmp/restored-baseline-json
python restore_json.py --gzip --output /tmp/restored-baseline-original-gzip
```

Outputs are exclusive and existing evidence is not replaced. The --gzip form
restores original trace filenames plus unchanged metadata/source snapshots.
No independent human sign-off is created by archival verification.
