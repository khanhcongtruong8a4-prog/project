"""Build a local, versioned backend without modifying installed ProxQP files.

The only algorithmic changes are the two support-function signs in dense
primal-infeasibility detection (ordinary and optional box constraints).
Both unpatched and patched builds can be retained for mechanism diagnosis.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import argparse, difflib, hashlib, importlib.metadata, json, shutil, subprocess, sysconfig
ROOT=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--unpatched',action='store_true');p.add_argument('--instrument',action='store_true')
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    if importlib.metadata.version('proxsuite')!='0.7.2':raise ValueError('Requires pinned ProxQP 0.7.2')
    site=Path(sysconfig.get_paths()['purelib']);include=site/'cmeel.prefix/include'
    eigen=site/'casadi/include/eigen3';source=include/'proxsuite/proxqp/dense/utils.hpp'
    text=source.read_text();original=text
    old='qpwork.b_scaled) +';start=text.index('global_primal_residual_infeasibility(')
    stop=text.index('global_dual_residual_infeasibility(',start)
    chunk=text[start:stop]
    if not a.unpatched:
        # negative_part(z) returns min(z,0), not max(-z,0).
        for needle in ['.dot(qpwork.u_scaled) -','.dot(qpwork.u_box_scaled) -']:
            if chunk.count(needle)!=1:raise ValueError('Upstream sign patch anchor differs')
            chunk=chunk.replace(needle,needle[:-1]+'+',1)
    if a.instrument:
        needle='res = lower_bound_2 <= upper_bound && lower_bound_1 <= -upper_bound;'
        log='''
  if (res) {
    std::cerr << std::setprecision(17) << "FARKAS_TRIGGER lower_support=" << lower_bound_1
      << " transpose_norm=" << lower_bound_2 << " threshold=" << upper_bound
      << " dz_norm=" << infty_norm(dz.to_eigen())
      << " dz_negative_count=" << (dz.to_eigen().array()<0).count()
      << " dz=" << dz.to_eigen().transpose() << std::endl;
  }
'''
        if chunk.count(needle)!=1:raise ValueError('Instrumentation anchor differs')
        chunk=chunk.replace(needle,needle+log)
    text=text[:start]+chunk+text[stop:]
    target=out/'include/proxsuite/proxqp/dense/utils.hpp';target.parent.mkdir(parents=True);target.write_text(text)
    diff=''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='ProxQP-0.7.2/utils.hpp',tofile='guarded-QP-reliability-v1/utils.hpp'))
    (out/'applied.patch').write_text(diff)
    wrapper=ROOT/'native/polynomial_completion_v2.cpp';library=out/'libpanda_completion.so'
    command=['g++','-std=c++17','-O3','-DNDEBUG','-fPIC','-shared','-fno-fast-math',
             '-I'+str(out/'include'),'-I'+str(include),'-I'+str(eigen),str(wrapper),'-o',str(library)]
    with (out/'build.log').open('x') as f:subprocess.run(command,check=True,stdout=f,stderr=subprocess.STDOUT)
    record={'version':'POLYNOMIAL_COMPLETION_V2','patched':not a.unpatched,'instrumented':a.instrument,
        'command':command,'compiler':subprocess.check_output(['g++','--version'],text=True).splitlines()[0],
        'upstream_proxsuite_version':'0.7.2','upstream_utils_sha256':sha(source),
        'upstream_headers_sha256':{str(f.relative_to(include)):sha(f) for f in sorted((include/'proxsuite').rglob('*.hpp'))},
        'Eigen_Core_sha256':sha(eigen/'Eigen/Core'),'wrapper_sha256':sha(wrapper),
        'applied_patch_sha256':sha(out/'applied.patch'),'library_sha256':sha(library),
        'original_installed_library_or_headers_modified':False}
    (out/'BUILD.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:record[k] for k in ['version','patched','instrumented','library_sha256']}))

if __name__=='__main__':main()
