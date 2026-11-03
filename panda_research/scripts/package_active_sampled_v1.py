"""Versioned new-work evidence ZIP plus small runnable numerical subset.

All new raw evidence is encoded losslessly and exactly restored by SHA256.
Older complete history stays in explicitly linked immutable annexes.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
import argparse,hashlib,json,shutil,subprocess,zipfile

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,d):Path(p).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')

README='''# IC2AI 2027 active-filter sampled-data remediation v1

Read panda_research/reports/active_sampled_data_v1/ACTIVE_FILTER_GATE_DECISION.md
and ACTIVE_FILTER_REFINEMENT_ROOT_CAUSE.md in that folder. All 19 frozen A2
cells freshly pass, with 120/120 refinement fields. T27 freshly passes 39
finite fixtures. All eight original active-filter failures reproduce exactly.
The separate genuinely active alpha10 challenge fails four peak comparisons.
Active-filter qualification and A3 are NO-GO; no Level1 or external signatures.

The moving-face local defect predicts the measured energy difference within
0.2% and peak difference within 1.2%, without fitting final outcomes. This is
conditional analysis and numerical attribution, not universal impossibility
or an interval safety certificate. Production control, original thresholds,
all 2644 prior tracked files and all failed experiments are unchanged.
The explicitly versioned first-order/hold-policy alternatives are proposals.

There are two downloads. ACTIVE_FILTER_REPRODUCTION.zip is the small runnable
source/analysis/T27 package, with no raw trace payloads. The full evidence ZIP
adds ALL new raw histories (27 simulation cells), all analysis arrays, retained
offline-analysis failures, and eight older raw traces used for exact historical
comparison. It restores exact original CTZ, gzip and NPZ bytes, not rounded or
downsampled data. Older complete history remains in HISTORICAL_ANNEX.json;
it is linked, not redundantly included. The small ZIP alone is not the complete
raw-evidence package. Raw evidence parts are <=20MiB for reliable downloads.

Use Linux and the exact recorded Python3.12.14 / pinned dependencies:

    python -m venv .venv
    .venv/bin/python -m pip install -r panda_research/requirements.lock.txt setuptools==80.9.0
    .venv/bin/python RUN_ACTIVE_FILTER.py --verify-only
    .venv/bin/python RUN_ACTIVE_FILTER.py --run-numerics --prefix independent_local_replay

The numerical command runs six mathematical plus three clock tests and the
39 exact KKT/Farkas solver fixtures. It needs no large evidence download.
“Local replay” is not an invented independent reviewer or signature.

From the FULL package, restore and recompute the trace analysis:

    .venv/bin/python RUN_ACTIVE_FILTER.py --restore --verify-only
    .venv/bin/python RUN_ACTIVE_FILTER.py --analyze-traces --prefix trace_replay

Restoration is standard-library-only, checks every original SHA, and refuses
to overwrite changed files. Exact container restoration uses the recorded
zlib1.3.2. Analyze-traces reruns the corrected read-only operator analysis and
modified-equation propagation. Failed gates remain failed during reproduction.

For all FRESH physical simulations using the original historical CLI provenance
checks, use the actual versioned source checkout; no fake Git history is made:

    git clone --branch active-sampled-data-v1 https://github.com/khanhcongtruong8a4-prog/project.git
    cd project/panda_research
    python scripts/replay_guarded_qp_reliability.py --prefix your_fresh_23
    python scripts/run_active_sampled_challenge_v1.py --output runs/active_sampled_data_v1/your_alpha10

Use the installed pinned Python for those commands. Prefixes/directories must
be new. The first command really runs seven original, twelve v4 and four legacy
active cells, and is EXPECTED to exit3 because the eight failures persist. The
second runs the separately frozen harder active alpha10 case and is EXPECTED
to exit3 because four peak comparisons fail. These are successful reproductions
of failed experiments, never a promotion to acceptance. The small ZIP does not
include the huge earlier source/input history needed by those frozen CLI hash
checks. Full checkout and older annex are explicitly separate provenance inputs.

No command in this package runs official A3 comparisons or claims Level1.
Neither a stored witness nor an unsafe extrapolated torque is a runtime fallback.
Wall-clock statistics under shared cloud load do not qualify a 1ms deadline.
M1 bounds and G2.5 planner start feasibility remain independent NO-GO gates.
'''

def main():
    p=argparse.ArgumentParser();p.add_argument('--payload',type=Path,required=True);p.add_argument('--numeric',type=Path,required=True)
    p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
    payload=a.payload.resolve();numeric=a.numeric.resolve();payload.mkdir(exist_ok=False);numeric.mkdir(exist_ok=False)
    tracked=subprocess.check_output(['git','ls-tree','-r','--name-only','HEAD'],cwd=REPO,text=True).splitlines()
    selected=[]
    prefixes=('panda_research/src/','panda_research/scripts/','panda_research/tests/','panda_research/policy/',
        'panda_research/native/','panda_research/reports/active_sampled_data_v1/','panda_research/inputs/active_sampled_data_v1/',
        'panda_research/runs/active_sampled_data_v1/','panda_research/reports/guarded_qp_reliability_v1/sd_v1_fresh/',
        'panda_research/runs/p1_r4/sd_v1_fresh_original_r4/')
    exact=['panda_research/baseline/model_manifest_v1.json','panda_research/baseline/panda_dynamics.py',
        'panda_research/inputs/action3/Project.rar','panda_research/requirements.lock.txt','panda_research/pyproject.toml',
        'panda_research/reports/pre_a3_blockers_v1/ISSUE_RESOLUTION_REPORT.md',
        'panda_research/reports/pre_a3_blockers_v1/active_filter_diagnosis/SUMMARY.json',
        'panda_research/reports/pre_a3_blockers_v1/final_analysis/CONTROL_PERIOD_LADDER.csv',
        'panda_research/reports/pre_a3_blockers_v1/m1_registry/M1_REGISTRY.json',
        'panda_research/reports/pre_a3_blockers_v1/g25_final_policy/SUMMARY.json']
    for n in tracked:
        keep=n.startswith(prefixes) or n in exact
        if n.startswith('panda_research/runs/guarded_qp_reliability_v1/sd_v1_fresh_'):keep=True
        if n.startswith('panda_research/runs/guarded_qp_reliability_v1/reliability_v1_fresh_active_E3/'):keep=True
        if n.startswith('panda_research/reports/a2_extended_v1/qp_bounds_evidence/run_v2/') and Path(n).suffix=='.json':keep=True
        if keep:selected.append(n)
    manuscript=json.loads((ROOT/'policy/v1.2.1/manuscript_source_hashes.json').read_text())['files']
    selected+=['panda_research/sources/manuscript_v1.2.1/'+n for n in manuscript];selected=sorted(set(selected))
    evidence=payload/'evidence';evidence.mkdir()
    for f in a.evidence.iterdir():shutil.copy2(f,evidence/f.name)
    encoded={}
    for pth in evidence.glob('*.index.json'):
        for r in json.loads(pth.read_text())['traces']:encoded[r['path']]={'sha256':r['sha256'],'size':r['size'],'encoding':'EXACT_CTZ_SHARED_XZ'}
    for pth in evidence.glob('*.regular.json'):
        for n,r in json.loads(pth.read_text())['files'].items():encoded[n]={'sha256':r['sha256'],'size':r['size'],'encoding':'EXACT_REGULAR_SHARED_XZ'}
    raw_selected={n for n in selected if n.endswith(('.ctz','.gz','.npz'))}
    if raw_selected!=set(encoded):raise ValueError('Exact evidence set mismatch: '+str(sorted(raw_selected^set(encoded))[:20]))
    logical={}
    for n in selected:
        src=REPO/n;logical[n]={'sha256':sha(src),'size':src.stat().st_size,'encoding':encoded.get(n,{}).get('encoding','REGULAR_FILE')}
        if n in encoded:
            if logical[n]['sha256']!=encoded[n]['sha256']:raise ValueError('Staged evidence changed: '+n)
        else:
            dst=payload/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    history={'previous_new_work_complete_evidence':{'artifact_commit':'a17e7c4f2f3f00a7030e2a09f235e534840b39d6','url':'https://github.com/khanhcongtruong8a4-prog/project/archive/a17e7c4f2f3f00a7030e2a09f235e534840b39d6.zip','sha256':'9738d83e7c9915d7f840b7313f5c94279a31cdd678a7a95fe552264ffebd35b6'},
        'older_complete_history':{'artifact_commit':'c271e443d33fe2a9f77a40eea9c79173c5609655','url':'https://github.com/khanhcongtruong8a4-prog/project/archive/c271e443d33fe2a9f77a40eea9c79173c5609655.zip','sha256':'65f808db22ec0be1e34854345cb17fdd8c129378ba276b3fd8ee99f59e65cbbc'},'linked_not_duplicated':True,'all_locally_accessible_during_this_task':True}
    dump(payload/'HISTORICAL_ANNEX.json',history)
    (payload/'RUN_ACTIVE_FILTER.py').write_text("from pathlib import Path\nimport sys\nsys.dont_write_bytecode=True\nsys.path.insert(0,str(Path(__file__).resolve().parent/'panda_research/scripts'))\nfrom reproduce_active_sampled_v1 import main\nraise SystemExit(main())\n")
    (payload/'README_ACTIVE_FILTER.md').write_text(README)
    source={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        'scope':'ALL_NEW_RAW_EVIDENCE_AND_SOURCE_PLUS_FOUR_LEGACY_COMPARISON_INPUTS','logical_files':logical,
        'encoded_files':encoded,'historical_annex':history,'fresh_simulation_cells':27,'official_A3':False,'Level1':False}
    dump(payload/'ACTIVE_SD_SOURCE_MANIFEST.json',source)
    downloads={str(f.relative_to(payload)):{'sha256':sha(f),'size':f.stat().st_size} for f in sorted(evidence.iterdir()) if f.is_file()}
    dump(payload/'EVIDENCE_DOWNLOAD_MANIFEST.json',{'files':downloads,'individual_binary_parts_at_most_bytes':20*(1<<20),'use_from_small_zip':True})
    (payload/'EVIDENCE_PARTS.md').write_text('# Evidence in small downloads\n\nDownload each linked file into evidence/ at the root of the small numerical package, then run RUN_ACTIVE_FILTER.py --restore --verify-only. All listed SHA256 values are checked. No float values are changed. Older history is linked separately in HISTORICAL_ANNEX.json.\n\n| File | Bytes | SHA256 |\n|---|---:|---|\n'+'\n'.join(f'| [{n}]({n}) | {r["size"]} | `{r["sha256"]}` |' for n,r in downloads.items())+'\n')
    for f in payload.rglob('*'):
        if f.is_file() and not f.is_relative_to(evidence):
            dst=numeric/f.relative_to(payload);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
    mini=dict(source);mini['scope']='SMALL_RUNNABLE_SOURCE_NUMERICAL_AND_REPORTS_NO_RAW_PAYLOADS'
    mini['logical_files']={n:r for n,r in logical.items() if n not in encoded}
    # Keep raw-file references as a declaration of what the small ZIP omits.
    mini['encoded_files']={};mini['raw_evidence_omitted_from_this_subset']=len(encoded)
    dump(numeric/'ACTIVE_SD_SOURCE_MANIFEST.json',mini)
    def manifest(folder):dump(folder/'ACTIVE_SD_PACKAGE_MANIFEST.json',{'files':{str(p.relative_to(folder)):{'sha256':sha(p),'size':p.stat().st_size} for p in sorted(folder.rglob('*')) if p.is_file()},'self_hash_excluded':True})
    manifest(numeric)
    mini_zip=payload/'ACTIVE_FILTER_REPRODUCTION.zip'
    with zipfile.ZipFile(mini_zip,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in sorted(numeric.rglob('*')):
            if f.is_file():z.write(f,str(f.relative_to(numeric)))
    manifest(payload)
    print(json.dumps({'source_commit':source['source_commit'],'logical_files':len(logical),'encoded_raw_files':len(encoded),
        'mini_zip_bytes':mini_zip.stat().st_size,'mini_zip_sha256':sha(mini_zip),
        'payload_file_bytes':sum(p.stat().st_size for p in payload.rglob('*') if p.is_file())},indent=2))

if __name__=='__main__':main()
