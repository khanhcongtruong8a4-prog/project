from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import copy,unittest
from types import SimpleNamespace as NS
import numpy as np
from panda_closed_loop.polynomial_hold_v2_4 import integrate
from panda_closed_loop.gauss_execution_audit_v2_4a import audit_step
from panda_closed_loop.stepper import ExecutionState
class AuditContracts(unittest.TestCase):
    def fixture(self):
        obs=NS(estimate=lambda q,v,z:np.zeros(7),derivative=lambda q,v,z,tau:-50*z-tau)
        model=NS(evaluate=lambda q,v:{'M':np.eye(7),'C':np.zeros((7,7)),'g':np.zeros(7),'F':np.zeros(7)})
        barriers=NS(qmin=np.full(7,-100.),qmax=np.full(7,100.),vmax=np.full(7,100.),entry_conditions=lambda q,v,tau:{'passed':True})
        system=NS(observer=obs,model=model,barriers=barriers,policy=NS(raw={'energy':{'k_r':[0]*7,'nonregenerative_smoothing':{'epsilon_W':1.}}}))
        state=ExecutionState(np.zeros(7),np.zeros(7),np.ones(7),0.)
        hold={'t0':0.,'delta':1.,'coefficients':np.zeros((4,7))}
        final,step=integrate(system,state,hold,.00025,.00025,NS(value=lambda t:np.ones(7)*100),lambda t:np.zeros(7))
        return system,hold,final,step
    def test_implicit_residual_is_the_declared_contract(self):
        system,hold,final,step=self.fixture();r=audit_step(system,hold,step,lambda t:np.zeros(7))
        self.assertTrue(r['passed']);z=-50*.00025;expected=(1+z/2+z*z/12)/(1-z/2+z*z/12)
        np.testing.assert_allclose(final.z,expected,rtol=0,atol=1e-14)
    def test_wrong_DOB_torque_is_detected(self):
        system,hold,final,step=self.fixture();bad=copy.deepcopy(step);bad['stage_rhs'][0,14]+=.1
        self.assertFalse(audit_step(system,hold,bad,lambda t:np.zeros(7))['passed'])
    def test_wrong_polynomial_stage_torque_is_detected(self):
        system,hold,final,step=self.fixture();bad=copy.deepcopy(step);bad['stage_torques'][0,0]+=.01
        self.assertFalse(audit_step(system,hold,bad,lambda t:np.zeros(7))['passed'])
if __name__=='__main__':unittest.main(verbosity=2)
