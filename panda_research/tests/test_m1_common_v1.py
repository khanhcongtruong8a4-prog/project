from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,json,unittest
import numpy as np
from numpy.polynomial.chebyshev import Chebyshev
from panda_dynamics import QMIN,QMAX,VMAX
from panda_closed_loop.a2_policy_v4 import build_amended_system
from panda_closed_loop.m1_common_domain_v1 import SHAPES,UNITS,CommonCoefficientEvaluator,common_domain,inertia_lower_lemma,canonical_sha,NumericalM1Registry
from panda_closed_loop.m1_margins_v1 import DevelopmentMarginProvider,exact_initial_pair_obstruction
from panda_closed_loop.config import digest
from test_p1_r3 import Results

def synthetic_registry(system):
    domain=common_domain(system.policy);entries={n:{'value':np.zeros(s).tolist(),'units':UNITS[n]} for n,s in SHAPES.items()}
    for n,v in [('m1',1.),('mbar_i',np.ones(7)),('Nbar_Q_il',np.eye(7)),('Nbar_il',np.eye(7))]:entries[n]['value']=np.asarray(v).tolist()
    return NumericalM1Registry({'domain':domain,'domain_sha256':canonical_sha(domain),'entries':entries,
        'registry_provenance_sha256':'0'*64,'scope':'SYNTHETIC_TEST_ONLY'})

class M1Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=build_amended_system();cls.s.geometry.function=cls.s.geometry.function.expand();cls.ev=CommonCoefficientEvaluator(cls.s)
    def test_inertia_lower_bound_is_analytic_not_a_sampled_minimum(self):
        proof=inertia_lower_lemma();self.assertGreater(proof['m1_lower'],0.);self.assertFalse(proof['sampled_eigenvalue_minimum_used_as_lower_bound'])
        for q in [(QMIN+QMAX)/2,QMIN,QMAX]:self.assertGreaterEqual(np.linalg.eigvalsh(self.s.model.evaluate(q)['M'])[0],proof['m1_lower'])
    def test_markov_constants_for_degree_five_are_exact(self):
        p=Chebyshev([0,0,0,0,0,1]);self.assertEqual(p.deriv(2)(1),200.);self.assertEqual(p.deriv(3)(1),840.)
        d=common_domain(self.s.policy);self.assertTrue(np.all(np.array(d['a_upper'])>np.array(d['Markov_ap_upper'])))
    def test_source_AD_derivatives_match_model_and_HOCBF_finite_differences(self):
        q=(QMIN+QMAX)/2+.01;v=np.linspace(-.3,.3,7);a=np.linspace(-2.,2.,7);values,_=self.ev.at(q,v,a)
        def outputs(x,y,z):
            e=self.s.model.evaluate(x,y,z);h,G,H=self.s.barriers.position_data(x)
            return e['ID'],G@z+np.einsum('i,kij,j->k',y,H,y)+10*G@y+25*h
        for axis,(x,n1,n2) in enumerate([(q,'L_u_q','L_h_q'),(v,'L_u_qd','L_h_qd'),(a,'L_u_qdd','L_h_qdd')]):
            du=[];dh=[]
            for j in range(7):
                step=np.eye(7)[j]*1e-6;args=[q.copy(),v.copy(),a.copy()];args[axis]+=step;up=outputs(*args);args[axis]-=2*step;down=outputs(*args)
                du.append((up[0]-down[0])/2e-6);dh.append((up[1]-down[1])/2e-6)
            np.testing.assert_allclose(values[n1],abs(np.array(du).T),rtol=3e-5,atol=2e-7)
            np.testing.assert_allclose(values[n2],abs(np.array(dh).T),rtol=3e-5,atol=2e-7)
    def test_full_margin_keeps_nonzero_rho_initial_and_factor_two(self):
        registry=synthetic_registry(self.s);vp=np.linspace(.1,.2,7);provider=DevelopmentMarginProvider(registry,self.s,vp,np.zeros(7),1.)
        d=provider.details(0.);np.testing.assert_array_equal(d['rho_r'],vp)
        np.testing.assert_allclose(d['b_vB'],3*vp,rtol=0,atol=1e-15)
        self.assertEqual(d['yb'],0.);self.assertTrue(np.all(d['chi_e']==0))
    def test_registry_cannot_promote_samples_or_supply_missing_zeros(self):
        registry=synthetic_registry(self.s)
        with self.assertRaises(ValueError):registry.require_certified()
        with self.assertRaises(ValueError):registry.values['mbar_i'][0]=0
        doc=registry.document;del doc['entries']['Nbar_il']
        with self.assertRaises(KeyError):NumericalM1Registry(doc)
    def test_actual_start_has_exact_represented_pair_obstruction(self):
        u=json.loads((ROOT/'runs/guarded_qp_reliability_v1/reliability_v1_fresh_v4_E3/cell_0.json').read_text())['endpoint']['QP']
        witness=exact_initial_pair_obstruction(self.s,u);self.assertEqual([r['joint'] for r in witness['rows'] if r['failed_exactly']],[1,3])
        self.assertFalse(witness['torque_actuated']);self.assertTrue(witness['factor_two_term_retained'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    result=unittest.TextTestRunner(verbosity=2,resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(M1Checks))
    paths=['src/panda_closed_loop/m1_common_domain_v1.py','src/panda_closed_loop/m1_margins_v1.py','tests/test_m1_common_v1.py']
    with a.report.open('x') as f:json.dump({'overall_pass':result.wasSuccessful(),'tests_run':result.testsRun,'checks':result.rows,
        'source_hashes':{n:digest(ROOT/n) for n in paths},'synthetic_bounds_not_robot_registry':True,'Level1':False},f,indent=2);f.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
