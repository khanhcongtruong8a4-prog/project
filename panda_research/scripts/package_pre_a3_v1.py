"""Compact, self-contained new-work package and numerical reproduction subset.

All prior source/failures remain in Git and the immutable historical annex.
This package includes new-work inputs/results plus the four legacy execution
traces actually used in diagnosis; it avoids duplicating the 656 MiB annex.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
import argparse,hashlib,json,shutil,subprocess,zipfile

def sha(p):return hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
def dump(p,d):Path(p).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')

WRAPPER='''from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent/'panda_research/scripts'))
from reproduce_pre_a3_v1 import main
raise SystemExit(main())
'''

README='''# IC2AI 2027 pre-A3 blocker investigation

Read panda_research/reports/pre_a3_blockers_v1/ISSUE_RESOLUTION_REPORT.md and
panda_research/policy/pre_a3_blockers_v1/TECHNICAL_DISPOSITION.json. A2's frozen 19-cell GO is
retained. Active-filter refinement, qualified M1 bounds, full G2.5 and A3 are
NO-GO. The rejected sampler is preserved as a failed development version.
T27 passes all 39 finite fixtures. No Level1 or external signatures are claimed.

This compact package includes all core source, unchanged model/policy audit
inputs, new numerical evidence, full raw evidence for six new simulation
cells, and four legacy active-filter execution traces used in diagnosis.
Other earlier raw history is preserved in the separately linked immutable
historical annex (HISTORICAL_ANNEX.json); it is not duplicated here.
The old 19-cell A2 data were reaudited in the full checkout. Their recorded
scientific digests and unchanged-source proof are included; another fresh
19-cell physical run is not claimed. Replaying every historical frozen CLI
requires the full original annex/checkout and all its original input checks.

Use Linux / Python3.12.14 and the recorded pinned versions. Exact CTZ container
restoration uses the recorded zlib1.3.2; every restored byte SHA is checked.

    python -m venv .venv
    .venv/bin/python -m pip install -r panda_research/requirements.lock.txt setuptools==80.9.0
    .venv/bin/python RUN_PRE_A3.py --verify-only
    .venv/bin/python RUN_PRE_A3.py --run-numerics --prefix my_numerical_replay
    .venv/bin/python RUN_PRE_A3.py --restore --diagnose-legacy --prefix my_trace_diagnosis
    .venv/bin/python RUN_PRE_A3.py --run-dynamics --prefix my_six_cell_replay

Numerical replay runs the 4 sampler contracts, 6 M1 contracts, 39 T27 fixtures,
rebuilds all 14 M1 tables from the fixed raw sampling protocol, reruns the
1,212 G2.5 point checks, and confirms the technical planner stop. Reproducing
NO-GO results is a successful reproduction, never a promotion to acceptance.
Dynamic replay reruns four candidate C4 and two original-AB2 ladder cells.
Fresh outputs are exclusive and previous failures are never overwritten.

The historical diagnosis restores exact raw CTZ files from evidence/. Their
array bytes and complete original ZIP containers are checked. No float values
are rounded, approximated or replaced with an optimum witness during packing.
Raw-feedback QPs are declared algorithmic steps, never fallback actuations.
QP guards, constraints, gains and numerical/acceptance targets are unchanged.

The bundled native backend and source build recipe retain their frozen SHA.
GCC builds are separately qualified if their binary SHA changes. The package
contains no venv, cache, Git history or external human signatures. For dynamic
replay it creates explicitly labeled LOCAL Git input-staging metadata for the
new frozen development declarations; historical commits are not reconstructed.
No official A3 comparison solver is invoked by any reproduction mode.
'''

def main():
    p=argparse.ArgumentParser();p.add_argument('--payload',type=Path,required=True);p.add_argument('--numeric',type=Path,required=True)
    p.add_argument('--staged-evidence',type=Path,required=True);a=p.parse_args();out=a.payload.resolve();out.mkdir(exist_ok=False)
    files=subprocess.check_output(['git','ls-tree','-r','--name-only','HEAD'],cwd=REPO,text=True).splitlines()
    selected=[]
    for n in files:
        keep=(n.startswith(('panda_research/src/','panda_research/scripts/','panda_research/tests/','panda_research/policy/',
            'panda_research/native/','panda_research/reports/pre_a3_blockers_v1/','panda_research/inputs/pre_a3_blockers_v1/',
            'panda_research/runs/pre_a3_blockers_v1/'))
            or n in ['panda_research/baseline/model_manifest_v1.json','panda_research/baseline/panda_dynamics.py',
                'panda_research/inputs/action3/Project.rar','panda_research/requirements.lock.txt','panda_research/pyproject.toml']
            or n.startswith('panda_research/reports/a2_extended_v1/qp_bounds_evidence/run_v2/fixture_') and n.endswith('.json')
            or n=='panda_research/reports/a2_extended_v1/qp_bounds_evidence/run_v2/t27_fixtures.json'
            or n in ['panda_research/reports/guarded_qp_reliability_v1/ROOT_CAUSE.md','panda_research/reports/guarded_qp_reliability_v1/COUNTEREXAMPLE_DIAGNOSIS.json',
                'panda_research/reports/guarded_qp_reliability_v1/DOWNLOAD_AND_RESTORATION_PROOF.json'])
        if n.startswith('panda_research/runs/guarded_qp_reliability_v1/reliability_v1_fresh_v4_E3/') and Path(n).name in [f'cell_{i}.json' for i in range(4)]:keep=True
        if n.startswith('panda_research/runs/guarded_qp_reliability_v1/reliability_v1_fresh_active_E3/') and (Path(n).name in ['summary.json']+[f'cell_{i}.json' for i in range(4)]+[f'cell_{i}_execution.ctz' for i in range(4)]):keep=True
        if keep:selected.append(n)
    manuscript=json.loads((ROOT/'policy/v1.2.1/manuscript_source_hashes.json').read_text())['files']
    selected+=['panda_research/sources/manuscript_v1.2.1/'+n for n in manuscript]
    selected=sorted(set(selected));encoded={}
    (out/'evidence').mkdir()
    for src in a.staged_evidence.iterdir():shutil.copy2(src,out/'evidence'/src.name)
    for index in (out/'evidence').glob('*.index.json'):
        for t in json.loads(index.read_text())['traces']:encoded[t['path']]={'sha256':t['sha256'],'size':t['size'],'encoding':'EXACT_CTZ_SHARED_XZ'}
    if {n for n in selected if n.endswith('.ctz')}!=set(encoded):raise ValueError('Task CTZ set differs from exact staged evidence')
    logical={}
    for n in selected:
        src=REPO/n;logical[n]={'sha256':sha(src),'size':src.stat().st_size,'encoding':encoded.get(n,{}).get('encoding','REGULAR_FILE')}
        if n in encoded:
            if encoded[n]['sha256']!=logical[n]['sha256']:raise ValueError('Staged CTZ differs: '+n)
        else:
            dest=out/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
    disposition=json.loads((ROOT/'policy/pre_a3_blockers_v1/TECHNICAL_DISPOSITION.json').read_text())
    dump(out/'HISTORICAL_ANNEX.json',disposition['prior_complete_history_archive'])
    (out/'RUN_PRE_A3.py').write_text(WRAPPER);(out/'PRE_A3_README.md').write_text(README)
    source={'scope':'COMPLETE_NEW_WORK_AND_REQUIRED_INPUTS_PLUS_RELEVANT_LEGACY_TRACE_INPUTS','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        'logical_files':logical,'encoded_CTZ':encoded,'prior_complete_history_is_separate_preserved_annex':True,
        'historical_annex':disposition['prior_complete_history_archive'],'old_19_cell_physical_rerun_claimed':False}
    dump(out/'PRE_A3_SOURCE_MANIFEST.json',source)
    numeric=a.numeric.resolve();numeric.mkdir(exist_ok=False)
    for src in sorted(out.rglob('*')):
        if src.is_file() and not str(src.relative_to(out)).startswith('evidence/'):
            dest=numeric/src.relative_to(out);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
    source_numeric=dict(source);source_numeric['scope']='RUNNABLE_NUMERICAL_REPRODUCTION_WITHOUT_RAW_TRACE_PAYLOADS';source_numeric['encoded_CTZ']={}
    source_numeric['logical_files']={n:r for n,r in logical.items() if n not in encoded}
    dump(numeric/'PRE_A3_SOURCE_MANIFEST.json',source_numeric)
    (numeric/'PRE_A3_README.md').write_text('''# Small pre-A3 numerical reproduction

This subset includes all core source and inputs for numerical reproduction
and fresh development simulation. Raw recorded CTZ files are in the separate
task evidence ZIP. The complete older history remains in the immutable annex
listed in HISTORICAL_ANNEX.json. Neither large download is needed for the
numerical commands below.

Read panda_research/reports/pre_a3_blockers_v1/ISSUE_RESOLUTION_REPORT.md.
A2's frozen 19-cell GO is retained. Active-filter refinement, M1 bound
qualification, G2.5 and A3 are NO-GO. All 39 finite T27 fixtures pass.
No independent signatures, official A3 experiments or Level1 claims.

With Linux / Python3.12.14 and the unchanged pinned dependency versions:

    python -m venv .venv
    .venv/bin/python -m pip install -r panda_research/requirements.lock.txt setuptools==80.9.0
    .venv/bin/python RUN_PRE_A3.py --verify-only
    .venv/bin/python RUN_PRE_A3.py --run-numerics --prefix my_numerical_replay

The numerical command runs 10 contracts and 39 T27 fixtures, rebuilds all 14
M1 entries, reproduces the held-out failures and all 1,212 G2.5 point checks,
and confirms the fail-closed planner gate. Reproducing a NO-GO is a successful
reproduction, never a promotion of a failed experiment to acceptance.

Optional fresh four-candidate/two-ladder simulation (exclusive new outputs):

    .venv/bin/python RUN_PRE_A3.py --run-dynamics --prefix my_six_cell_replay

Dynamic replay creates explicitly labeled LOCAL Git metadata for the frozen
new declarations. It does not reconstruct historical commits or signatures.
The rejected sampler remains rejected. Recorded legacy-trace diagnosis with
--restore/--diagnose-legacy requires the task evidence ZIP. The old historical
frozen CLIs need their full original data/annex and retain their original checks.
''')
    def manifest(folder,scope):
        dump(folder/'PRE_A3_PACKAGE_MANIFEST.json',{'scope':scope,'files':{str(p.relative_to(folder)):{'sha256':sha(p),'size':p.stat().st_size} for p in sorted(folder.rglob('*')) if p.is_file()},'excludes_self_hash':True})
    manifest(numeric,'NUMERICAL_SUBSET_NO_RAW_TRACE_FILES')
    with zipfile.ZipFile(out/'NUMERICAL_REPRODUCTION.zip','x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(numeric.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(numeric)))
    manifest(out,'COMPLETE_NEW_WORK_PLUS_REQUIRED_LEGACY_TRACE_INPUTS_OTHER_HISTORY_IN_IMMUTABLE_ANNEX')
    print('Selected logical files',len(logical),'exact CTZ',len(encoded),'numerical ZIP bytes',(out/'NUMERICAL_REPRODUCTION.zip').stat().st_size,
        'physical payload bytes',sum(p.stat().st_size for p in out.rglob('*') if p.is_file()),flush=True)

if __name__=='__main__':main()
