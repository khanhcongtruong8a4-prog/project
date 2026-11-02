"""Freeze and fill every core M1 coefficient entry; keep certification separate."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,json,hashlib,time
import numpy as np
from scipy.stats import qmc
from panda_closed_loop.a2_policy_v4 import build_amended_system
from panda_closed_loop.m1_common_domain_v1 import SHAPES,UNITS,CommonCoefficientEvaluator,common_domain,inertia_lower_lemma,canonical_sha
from panda_closed_loop.readiness import m1_registry
from panda_closed_loop.logging import json_values


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    freeze=json.loads((ROOT/'policy/pre_a3_blockers_v1/M1_PREDECLARATION.json').read_text())
    for n,h in freeze['source_sha256'].items():
        if hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h:raise ValueError('Frozen M1 source changed: '+n)
    a.output.mkdir(parents=True,exist_ok=False);system=build_amended_system();domain=common_domain(system.policy)
    if domain!=freeze['common_domain']:raise ValueError('Frozen M1 domain differs')
    proof=inertia_lower_lemma();evaluator=CommonCoefficientEvaluator(system)
    lower=np.r_[domain['q_phase_lower'],domain['v_lower'],domain['a_lower']]
    upper=np.r_[domain['q_phase_upper'],domain['v_upper'],domain['a_upper']]
    sampler=qmc.Sobol(21,scramble=True,seed=domain['seed']);points=qmc.scale(sampler.random_base2(10),lower,upper)
    train=points[:512];holdout=points[512:768]
    anchors=[]
    for index in range(4):
        c=json.loads((ROOT/f'runs/guarded_qp_reliability_v1/reliability_v1_fresh_v4_E3/cell_{index}.json').read_text())['endpoint']['QP']
        q=(np.array(c['q'])+np.pi)%(2*np.pi)-np.pi
        anchors.append(np.r_[q,c['qd'],np.zeros(7)])
    from panda_dynamics import QMIN,QMAX
    anchors.append(np.r_[(QMIN+QMAX)/2,np.zeros(14)]);train=np.vstack([train,anchors])
    names=[n for n in SHAPES if n!='m1'];raw={};extrema={};eigen={}
    for label,coordinates in [('training',train),('heldout',holdout)]:
        batches={n:[] for n in names};eigen[label]=[]
        for k,x in enumerate(coordinates):
            values,minimum=evaluator.at(x[:7],x[7:14],x[14:]);eigen[label].append(minimum)
            for n in names:batches[n].append(values[n])
            if k%128==0:print(label,k,'evaluated',flush=True)
        for n in names:
            raw[label+'__'+n]=np.array(batches[n]);extrema[label+'__'+n]=np.max(raw[label+'__'+n],axis=0)
        raw[label+'__coordinates']=coordinates;raw[label+'__observed_min_eigenvalue']=np.array(eigen[label])
    np.savez_compressed(a.output/'RAW_M1_SAMPLES.npz',**raw)
    grid_sha=hashlib.sha256(train.tobytes()+holdout.tobytes()).hexdigest()
    requirements={x['name']:x for x in m1_registry(system.policy,'stage1_tightened')['entries']}
    entries={};exceedances={}
    for n in SHAPES:
        v=proof['m1_lower'] if n=='m1' else extrema['training__'+n]
        entries[n]={'value':json_values(v),'shape':list(SHAPES[n]),'units':UNITS[n],
            'source':requirements[n]['source'],'direction':'LOWER' if n=='m1' else 'UPPER_ESTIMATE_ONLY',
            'evidence_level':'ANALYTIC_IDEAL_MODEL_LEMMA' if n=='m1' else 'FINITE_TRAINING_SAMPLE_EXTREMUM_NOT_CERTIFIED_UPPER_BOUND',
            'certified_for_full_floating_robot_domain':False,'missing_values_substituted_as_zero':False}
        if n!='m1':
            trainmax=extrema['training__'+n];testmax=extrema['heldout__'+n];ex=testmax>trainmax
            exceedances[n]={'component_count':int(np.sum(ex)),'component_total':int(np.size(ex)),
                'maximum_absolute_exceedance':float(max(0.,np.max(testmax-trainmax))),
                'heldout_maximum':testmax.tolist(),'training_extremum_retained_unchanged':True}
    source_hashes=freeze['source_sha256'];document={'version':'M1_NUMERICAL_COMMON_DOMAIN_REGISTRY_V1','domain':domain,
        'domain_sha256':canonical_sha(domain),'grid_sha256':grid_sha,'source_sha256':source_hashes,'entries':entries,
        'inertia_lower_lemma':proof,'training_points':len(train),'heldout_points':len(holdout),'heldout_exceedances':exceedances,
        'observed_eigenvalue_minimum_NOT_used_as_bound':min(min(v) for v in eigen.values()),
        'all_14_core_coefficient_entries_present':True,'registry_completeness':'COMPLETE_NUMERIC_COEFFICIENT_TABLE',
        'upper_bound_qualification':'NO_GO_FINITE_SAMPLES_ARE_NOT_DOMAIN_SUPREMA','Level1':False,
        'official_stage1_or_A3_approval':False,'external_independent_signatures':None}
    document['registry_provenance_sha256']=canonical_sha(document)
    with (a.output/'M1_REGISTRY.json').open('x') as f:json.dump(document,f,indent=2,allow_nan=False);f.write('\n')
    print('Core entries',len(entries),'heldout exceeded components',sum(d['component_count'] for d in exceedances.values()),flush=True)

if __name__=='__main__':main()
