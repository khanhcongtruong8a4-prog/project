"""Build the small runnable source distribution, leaving bulk evidence separate."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
REPO=Path(__file__).resolve().parents[2]
import argparse,hashlib,json,subprocess,zipfile

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
README='''# Panda A2 v2.4b — compact runtime/source package

This is the SMALL download. It contains the unchanged numerical implementation,
all normative policies/inputs, tested native QP libraries, tests, mathematical
notes and lightweight result/failure summaries. Bulk historical traces are
omitted. One original ~11 MB trace fixture is retained for the unchanged v4
unit tests. No stored witness is used as a runtime control fallback.

Linux x86-64 and Python 3.12.14 are the recorded platform. Git is required for
local policy staging. Native libraries and their source/build records are
included. Python dependencies are installed separately (not bundled):

    python3.12 -m venv .venv
    .venv/bin/python -m pip install -r panda_research/requirements-compact.lock.txt
    .venv/bin/python RUN_COMPACT_A2.py --verify-only
    .venv/bin/python RUN_COMPACT_A2.py --prefix my_tests

The default command executes 65 mathematical/audit/legacy contracts plus all
39 T27 fixtures, with real exit-status and test-count checks. No old summary
is substituted for a current test outcome. The minimal dependency lock keeps
the original NumPy/SciPy/CasADi/ProxSuite/cmeel versions; optional independent
Pinocchio/MuJoCo model-review tools use the separate original full lockfile.

To generate one complete new closed-loop trajectory:

    .venv/bin/python RUN_COMPACT_A2.py --candidate alpha10 --cell 0 --prefix my_cell

To regenerate all seven original, twelve extended and eight active-candidate
cells, including refinements and complete guard/KKT/GL audits:

    .venv/bin/python RUN_COMPACT_A2.py --all --prefix my_full_replay

Full numerical replays are computationally substantial and generate large raw
traces LOCALLY. Existing raw result/audit flags and their separately versioned
v2.4a/v2.4b verification corrections are retained honestly in the outputs.
Fail-closed behavior, original dynamics/gains/guards/thresholds and all
mathematical execution functions are unchanged.

## Precisely different provenance scope

COMPACT_MANIFEST.json verifies every included byte and identifies omissions.
The compact plan-file adapter binds ONLY the normative plan loader of the
unchanged numerical function bytecode; it does not change control, dynamics,
integration, constraints or acceptance formulas. Source and normative inputs
are checked before motion. Original historical archive-integrity CLIs cannot
validate omitted raw files. Those integrity gates are explicitly NOT RUN in
the compact flow, never represented as passes. Use this entry point rather
than the older full-history wrappers, which intentionally require the archive.

The previously completed acceptance and failure history are read-only reports.
A new numerical replay gets its own fresh results; there is no new universal
or certified GO merely from unpacking this distribution. No A3 comparisons,
Level1 certificate, hardware timing or certified true-ODE bounds are claimed.

The complete unchanged history remains at the immutable full-source annex:
https://github.com/khanhcongtruong8a4-prog/project/archive/c1d0fd2eb7ac05a955b2d75ce6ff01ea45f543c8.zip
You do NOT need that multi-GB download for the compact test/runtime commands.
'''
RUN='''from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent/'panda_research/scripts'))
from compact_a2_runtime import main
if __name__=='__main__':raise SystemExit(main())
'''

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    tracked=[x.decode() for x in subprocess.check_output(['git','ls-files','-z'],cwd=REPO).split(b'\0') if x]
    selected=set()
    for n in tracked:
        src=REPO/n
        if n.startswith('panda_research/') and not n.startswith(('panda_research/runs/','panda_research/reports/')):selected.add(n)
        elif n.startswith('panda_research/reports/active_remediation_v2/'):
            if '/final_v2_4b/' in n or Path(n).name in ['RECOVERY.json','PRESERVATION_AUDIT.json','DELIVERY_VERIFICATION.json']:
                selected.add(n)
        elif n.startswith('panda_research/reports/a2_extended_v1/actual_extended_qp_diagnostics/') and src.suffix=='.json':selected.add(n)
    selected.update([
        'panda_research/reports/a2_extended_v1/qp_bounds_evidence/run_v2/t27_fixtures.json',
        'panda_research/reports/a2_extended_v1/qp_bounds_evidence/run_v2/fixture_09.json',
        'panda_research/runs/a2_extended_v2/E3_0391c5b/cell_0.json',
        'panda_research/runs/a2_extended_v4/E3_c02f908/cell_0.json'])
    selected.update(['panda_research/scripts/compact_a2_runtime.py','panda_research/scripts/package_compact_a2.py','panda_research/requirements-compact.lock.txt',
                     'panda_research/runs/a2_extended_v2/E3_0391c5b/cell_0_execution.ctz'])
    # Exact, small prerequisites for the original component/source regression
    # metadata. This does not make a missing old raw-trace integrity gate pass.
    for n in ['reports/p1_v1.2.2_r3/engineering/action3/run.json','reports/p1_v1.2.2_r3/engineering/legacy/verification_run.json']:
        selected.add('panda_research/'+n)
        for rel in json.loads((REPO/'panda_research'/n).read_text())['code_and_input_hashes']:selected.add('panda_research/'+rel)
    virtual={'README_COMPACT.md':README.encode(),'RUN_COMPACT_A2.py':RUN.encode()}
    files={n:{'size':(REPO/n).stat().st_size,'sha256':sha(REPO/n)} for n in sorted(selected)}
    for n,b in virtual.items():files[n]={'size':len(b),'sha256':hashlib.sha256(b).hexdigest()}
    omitted={n:{'size':(REPO/n).stat().st_size,'sha256':sha(REPO/n)} for n in tracked if n not in selected and n.startswith(('panda_research/reports/','panda_research/runs/'))}
    manifest={'version':'A2_COMPACT_SOURCE_DISTRIBUTION_V1','scientific_source_commit':'c1d0fd2eb7ac05a955b2d75ce6ff01ea45f543c8',
              'archive_history_integrity_gate':'NOT_RUN_OMITTED_FROM_COMPACT','controller_or_threshold_changes':False,
              'files':files,'omitted_historical_payloads':omitted,'omitted_historical_bytes':sum(x['size'] for x in omitted.values()),'manifest_self_hash_excluded':True}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n in sorted(selected):z.write(REPO/n,n)
        for n,b in virtual.items():z.writestr(n,b)
        z.writestr('COMPACT_MANIFEST.json',json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    digest=sha(a.output);a.output.with_suffix(a.output.suffix+'.sha256').write_text(digest+'  '+a.output.name+'\n')
    print(json.dumps({'zip':str(a.output),'bytes':a.output.stat().st_size,'files':len(files),'sha256':digest,'omitted_historical_bytes':manifest['omitted_historical_bytes']},indent=2))
if __name__=='__main__':main()
