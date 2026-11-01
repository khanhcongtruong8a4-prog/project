"""Action 3 component/fixture tests. No run here is official A2 or G2.5."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import argparse
import inspect
import json
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np
from scipy.integrate import solve_ivp
import pinocchio as pin
from panda_dynamics import PandaDynamics, QMIN, QMAX, VMAX, TAUMAX, dual_harmonic_disturbance, disturbance_bounds
from panda_closed_loop.config import Policy
from panda_closed_loop.reference import ReferenceSample, MeasuredStateReference
from panda_closed_loop.observer import MomentumObserver, ObserverEnvelope, DisturbanceBounds
from panda_closed_loop.controller import SlotineLiController
from panda_closed_loop.geometry import FlangeGeometry
from panda_closed_loop.barriers import BarrierEvaluator, AffineRows
from panda_closed_loop.qp import HardSafetyQP, QPResult, project_torque_box
from panda_closed_loop.stepper import HeldTorqueHarness, ExecutionState, HoldSchedule, ProtectiveStop
from panda_closed_loop.margins import disturbance_allowances, velocity_margin
from panda_closed_loop.assembly import build_components
from panda_closed_loop.logging import TraceLogger
from reference_model import build_reference_urdf

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = {}


def serial(value):
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, dict): return {k: serial(v) for k,v in value.items()}
    if isinstance(value, (tuple,list)): return [serial(v) for v in value]
    return value


class IdentityPlant:
    """Explicit synthetic numerical fixture; NOT a substitute Panda plant."""
    def evaluate(self, q, qd=None, qdd=None):
        return {'M': np.eye(7), 'C': np.zeros((7,7)), 'g': np.zeros(7), 'F': np.zeros(7)}


class PolynomialGeometry:
    """Synthetic f=[q0+.1q0^2,q1,q2], so W=(1+.2q0)^2."""
    def evaluate(self, q):
        q = np.asarray(q)
        j = np.eye(3,7); j[0,0] = 1+.2*q[0]
        gradient = np.zeros(7); gradient[0] = .4*(1+.2*q[0])
        hessian = np.zeros((7,7)); hessian[0,0] = .08
        return {'f': np.r_[q[0]+.1*q[0]**2,q[1:3]], 'Jv': j, 'W': (1+.2*q[0])**2,
                'gradient_W': gradient, 'hessian_W': hessian}


def synthetic_barrier(model):
    return BarrierEvaluator(model, PolynomialGeometry(), -2*np.ones(7), 2*np.ones(7),
                            VMAX, TAUMAX, .1, 5, 5, 5)


def box_rows(extra_G=None, extra_c=None, extra_scale=None):
    G = np.vstack([-np.eye(7),np.eye(7)])
    c = np.r_[TAUMAX,TAUMAX]
    scales = np.r_[TAUMAX,TAUMAX]
    if extra_G is not None:
        G = np.vstack([G,extra_G]); c=np.r_[c,extra_c]; scales=np.r_[scales,extra_scale]
    return AffineRows(G,c,scales,tuple('fixture_row_'+str(i) for i in range(len(c))),tuple(['fixture SI']*len(c)))


class FixedTorque:
    """Test-only held-input oracle, no claim to implement a safety filter."""
    def __init__(self,tau): self.tau=np.array(tau);self.calls=0
    def solve(self, nominal, rows):
        self.calls+=1
        return QPResult(self.tau.copy(),'SYNTHETIC_FIXED_TORQUE_FIXTURE',False,{'intervention_Nm':float(np.linalg.norm(self.tau-nominal))})


class Action3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=Policy.load();cls.source_audit=cls.policy.source_audit()
        cls.model=PandaDynamics();cls.geometry=FlangeGeometry(cls.model)
        cls.q0=(QMIN+QMAX)/2
        cls.wmin=cls.geometry.floor_at(cls.q0)
        p=cls.policy
        cls.barrier=BarrierEvaluator(cls.model,cls.geometry,QMIN,QMAX,VMAX,TAUMAX,cls.wmin,p.alpha1,p.alpha2,p.alpha_v)

    def assertClose(self,a,b,atol=1e-10,rtol=0):
        np.testing.assert_allclose(a,b,atol=atol,rtol=rtol)

    def test_policy_byte_hash_units_and_source_cells(self):
        p=self.policy
        self.assertEqual(p.delta,.001);self.assertEqual(p.h,.00025)
        self.assertEqual(p.ko,(20.,)*7);self.assertEqual(p.lambdas,(5.,)*7)
        self.assertTrue(all(r['matches'] for r in self.source_audit['workbook_cell_audit']))
        self.assertTrue(self.source_audit['canonical_equations_match'])
        mismatches=[r['file'] for r in self.source_audit['manuscript'] if not r['matches']]
        self.assertEqual(set(mismatches),{'main.tex','Project.rar'})
        DIAGNOSTICS['source_audit']=self.source_audit

    def test_invalid_nonfinite_inputs_and_no_silent_defaults(self):
        observer=MomentumObserver(self.model,self.policy.ko)
        controller=SlotineLiController(self.model,self.policy.lambdas,self.policy.kappa)
        q=self.q0;v=np.zeros(7);sample=ReferenceSample(q,v,v)
        invalid=[np.zeros(6),np.zeros((7,2)),np.full(7,np.nan),np.full(7,np.inf)]
        count=0
        for bad in invalid:
            calls=[lambda:observer.initialize(bad,v),lambda:observer.estimate(q,bad,v),
                   lambda:observer.derivative(q,v,v,bad),lambda:controller.command(q,v,sample,bad),
                   lambda:self.barrier.rows(q,v,v,bad),lambda:self.geometry.evaluate(bad),
                   lambda:ReferenceSample(q,v,bad)]
            for call in calls:
                with self.assertRaises(ValueError):call()
                count+=1
        for call in [lambda:MomentumObserver(self.model,np.zeros(7)),lambda:SlotineLiController(self.model,np.ones(7),0),
                     lambda:HoldSchedule(.001,.0003),lambda:HoldSchedule(0,.001),
                     lambda:ObserverEnvelope(np.ones(7),np.zeros(7),-np.ones(7)),
                     lambda:self.barrier.rows(q,v,v,-np.ones(7))]:
            with self.assertRaises(ValueError):call()
            count+=1
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'tampered.json';path.write_text(self.policy.raw_json)
            with self.assertRaises(ValueError):Policy.load(path)
        DIAGNOSTICS['invalid_inputs']={'rejected_calls':count+1,'no_missing_M1_zero_substitution':True}

    def test_flange_jacobian_world_frame_and_manipulability_derivatives(self):
        ref=pin.buildModelFromUrdf(str(build_reference_urdf()));data=ref.createData()
        errors=[]
        for q in [self.q0,self.q0+np.array([.1,-.1,.2,.1,-.1,.1,.1])]:
            out=self.geometry.evaluate(q)
            J=pin.computeFrameJacobian(ref,data,q,ref.getFrameId('panda_link8'),pin.ReferenceFrame.LOCAL_WORLD_ALIGNED)[:3]
            self.assertClose(out['Jv'],J,atol=1e-10,rtol=1e-9)
            self.assertClose(out['W'],np.linalg.det(J@J.T),atol=1e-12)
            eps=2e-5;grad=np.zeros(7);hessian=np.zeros((7,7))
            for i in range(7):
                dq=np.eye(7)[i]*eps
                plus,minus=self.geometry.evaluate(q+dq),self.geometry.evaluate(q-dq)
                grad[i]=(plus['W']-minus['W'])/(2*eps)
                hessian[:,i]=(plus['gradient_W']-minus['gradient_W'])/(2*eps)
            self.assertClose(out['gradient_W'],grad,atol=5e-9)
            self.assertClose(out['hessian_W'],hessian,atol=1e-7)
            errors.append({'J_max_error':float(np.max(abs(out['Jv']-J))), 'gradient_error':float(np.max(abs(out['gradient_W']-grad))),
                           'hessian_error':float(np.max(abs(out['hessian_W']-hessian)))})
        DIAGNOSTICS['geometry']=errors

    def test_observer_moving_initialization_bound_and_replan(self):
        obs=MomentumObserver(self.model,self.policy.ko)
        v=np.linspace(-.12,.16,7);z=obs.initialize(self.q0,v)
        self.assertGreater(np.linalg.norm(z),0)
        self.assertClose(obs.estimate(self.q0,v,z),np.zeros(7),atol=1e-14)
        dbar,rate=disturbance_bounds();bounds=DisturbanceBounds(dbar,rate)
        envelope=ObserverEnvelope(self.policy.ko,bounds.magnitude,bounds.rate)
        self.assertTrue(np.all(abs(dual_harmonic_disturbance(0))<=envelope.value(0)))
        restarted=envelope.restart_at(.75)
        self.assertClose(restarted.value(1.25),envelope.value(1.25))
        with self.assertRaises(ValueError):envelope.value(-.01)

    def test_observer_identity_applied_torque_feedback_and_no_truth_argument(self):
        obs=MomentumObserver(self.model,self.policy.ko);q=self.q0;v=np.linspace(-.2,.2,7)
        z=obs.initialize(q,v)+.01;nom=self.model.evaluate(q,v)['g']
        applied=nom+np.linspace(.03,.07,7);d=dual_harmonic_disturbance(.2)
        e=self.model.evaluate(q,v);qdd=self.model.acceleration(q,v,applied,d)
        eps=2e-6
        pplus=self.model.evaluate(q+eps*v)['M']@(v+eps*qdd)
        pminus=self.model.evaluate(q-eps*v)['M']@(v-eps*qdd)
        pdot=(pplus-pminus)/(2*eps)
        ddhat=obs.derivative(q,v,z,applied)+np.array(self.policy.ko)*pdot
        self.assertClose(ddhat,np.array(self.policy.ko)*(d-obs.estimate(q,v,z)),atol=2e-7)
        wrong=obs.derivative(q,v,z,nom)+np.array(self.policy.ko)*pdot
        self.assertGreater(np.max(abs(wrong-ddhat)),.5)
        for function in [obs.derivative,obs.estimate,SlotineLiController.command]:
            self.assertNotIn('true_d',inspect.signature(function).parameters)
            self.assertNotIn('disturbance',inspect.signature(function).parameters)

    def test_tracking_sign_initialization_and_differential_identity(self):
        ctrl=SlotineLiController(self.model,self.policy.lambdas,self.policy.kappa)
        q=self.q0;v=np.linspace(-.1,.1,7);a=np.linspace(-.2,.2,7);dhat=np.linspace(-.05,.05,7)
        ref=MeasuredStateReference(q,v,3.)
        _,state=ctrl.command(q,v,ref.sample(3.),dhat)
        self.assertClose(state['e'],0);self.assertClose(state['edot'],0);self.assertClose(state['s'],0)
        sample=ReferenceSample(q+.01*np.arange(1,8),v+.02,a)
        u,data=ctrl.command(q,v,sample,dhat);d=dual_harmonic_disturbance(3.)
        correction=np.linspace(-.1,.1,7);actual=u+correction
        qdd=self.model.acceleration(q,v,actual,d)
        sdot=sample.qdd-qdd+np.array(self.policy.lambdas)*(sample.qd-v)
        e=self.model.evaluate(q,v)
        self.assertClose(e['M']@sdot+(e['C']+self.policy.kappa*e['M'])@data['s'],-(d-dhat)-correction,atol=3e-13)
        eps=1e-6
        ep=(sample.q+eps*sample.qd+.5*eps**2*sample.qdd)-(q+eps*v+.5*eps**2*qdd)
        em=(sample.q-eps*sample.qd+.5*eps**2*sample.qdd)-(q-eps*v+.5*eps**2*qdd)
        self.assertClose((ep-em)/(2*eps),sample.qd-v,atol=2e-10)
        moving=ctrl.command(q+.001*np.ones(7),v,ref.sample(3.),dhat)[0]
        stationary=ctrl.command(q-.001*np.ones(7),v,ref.sample(3.),dhat)[0]
        self.assertNotEqual(float(np.linalg.norm(moving-stationary)),0.)

    def test_all_43_affine_rows_against_independent_direct_equations(self):
        q=self.q0+.01;v=np.linspace(-.1,.1,7);dhat=np.linspace(-.05,.05,7)
        varpi=np.linspace(.01,.04,7);tau=self.model.evaluate(q,v)['g']+.1
        b=self.barrier;rows=b.rows(q,v,dhat,varpi)
        self.assertEqual(rows.G.shape,(43,7));self.assertEqual(len(set(rows.names)),43)
        e=self.model.evaluate(q,v);N=np.linalg.solve(e['M'],np.eye(7))
        accel=np.linalg.solve(e['M'],tau+dhat-e['C']@v-e['g']-e['F'])
        h,gradient,hess=b.position_data(q)
        position=np.array([gradient[j]@accel+v@hess[j]@v+(b.alpha1+b.alpha2)*(gradient[j]@v)+b.alpha1*b.alpha2*h[j]
                           -np.sum(abs(gradient[j]@N)*varpi) for j in range(15)])
        direct=np.r_[position,-accel+b.alpha_v*(VMAX-v)-abs(N)@varpi,
                     accel+b.alpha_v*(VMAX+v)-abs(N)@varpi,TAUMAX-tau,TAUMAX+tau]
        self.assertClose(rows.slacks(tau),direct,atol=2e-12)
        eps=1e-4;fd=np.column_stack([(rows.slacks(tau+np.eye(7)[k]*eps)-rows.slacks(tau-np.eye(7)[k]*eps))/(2*eps) for k in range(7)])
        self.assertClose(fd,rows.G,atol=2e-8,rtol=1e-8)
        self.assertClose(rows.scales,np.r_[QMAX-QMIN,QMAX-QMIN,b.w_min**2,VMAX,VMAX,TAUMAX,TAUMAX])
        self.assertEqual(rows.units[14],'m^6/s^2')
        reserves=b.planner_reserves(self.policy)
        self.assertClose(reserves['joint_HOCBF_rad_s2'],1e-4*(QMAX-QMIN))
        self.assertAlmostEqual(reserves['velocity_CBF_rad_s2'],.0002175)
        DIAGNOSTICS['affine_rows']={'count':43,'max_torque_finite_difference_error':float(np.max(abs(fd-rows.G))),
            'row_names':rows.names,'row_units':rows.units,'planner_reserves':reserves}

    def test_entry_conditions_include_psi1_velocity_manipulability_and_torque(self):
        b=self.barrier
        self.assertTrue(b.entry_conditions(self.q0,np.zeros(7))['passed'])
        q=self.q0.copy();q[0]=QMAX[0]+.01
        self.assertFalse(b.entry_conditions(q,np.zeros(7))['passed'])
        q=self.q0.copy();q[0]=QMAX[0]-.001;v=np.zeros(7);v[0]=.1
        self.assertLess(b.entry_conditions(q,v)['psi1'][0],0)
        self.assertFalse(b.entry_conditions(self.q0,2*VMAX)['passed'])
        self.assertFalse(b.entry_conditions(self.q0,np.zeros(7),TAUMAX+1e-12)['passed'])

    def test_qp_feasible_zero_intervention_active_and_infeasible_fixtures(self):
        qp=HardSafetyQP(TAUMAX,self.policy.raw['solver']['QP_settings'])
        zero=qp.solve(np.zeros(7),box_rows())
        self.assertFalse(zero.stop_requested);self.assertLess(np.linalg.norm(zero.applied),1e-6)
        G=-np.eye(7)[0:1];c=np.array([1.])
        active=qp.solve(np.r_[3.,np.zeros(6)],box_rows(G,c,np.ones(1)))
        self.assertFalse(active.stop_requested)
        self.assertClose(active.applied,np.r_[1.,np.zeros(6)],atol=5e-8)
        for solved in [zero,active]:
            self.assertLessEqual(solved.diagnostics['normalized_primal'],1e-9)
            self.assertLessEqual(solved.diagnostics['scaled_stationarity'],1e-9)
        impossible=qp.solve(np.zeros(7),box_rows(np.vstack([np.eye(7)[0],-np.eye(7)[0]]),np.array([-2.,1.]),np.ones(2)))
        self.assertTrue(impossible.stop_requested);self.assertIsNone(impossible.applied)
        self.assertIn('DISABLED',impossible.diagnostics['recovery'])
        clipped=project_torque_box(2*TAUMAX,TAUMAX)
        self.assertClose(clipped,TAUMAX)
        DIAGNOSTICS['QP_synthetic_fixtures']={'zero':zero.diagnostics,'active':active.diagnostics,'infeasible_status':impossible.status,
                                            'scope':'COMPONENT NUMERICS ONLY, not full T27'}

    def test_approved_panda_initial_component_is_infeasible_and_stops(self):
        q=self.q0;v=np.zeros(7);varpi=.02*TAUMAX
        rows=self.barrier.rows(q,v,np.zeros(7),varpi)
        N=np.linalg.solve(self.model.evaluate(q)['M'],np.eye(7))
        margin=abs(N)@varpi
        pair_limit=self.policy.alpha_v*VMAX
        self.assertTrue(np.any(margin>pair_limit))
        qp=HardSafetyQP(TAUMAX,self.policy.raw['solver']['QP_settings'])
        solved=qp.solve(self.model.evaluate(q)['g'],rows)
        self.assertTrue(solved.stop_requested);self.assertIsNone(solved.applied)
        obs=MomentumObserver(self.model,self.policy.ko);dbar,rate=disturbance_bounds()
        harness=HeldTorqueHarness(self.model,obs,SlotineLiController(self.model,self.policy.lambdas,self.policy.kappa),
            self.barrier,qp,ObserverEnvelope(self.policy.ko,dbar,rate),MeasuredStateReference(q,v,0.),
            HoldSchedule(self.policy.delta,self.policy.h),dual_harmonic_disturbance)
        state=ExecutionState(q,v,obs.initialize(q,v),0.)
        with self.assertRaises(ProtectiveStop):harness.advance(state)
        self.assertEqual(state.t,0.)
        DIAGNOSTICS['PANDA_APPROVED_INITIAL_COMPONENT']={
            'scope':'STATIC COMPONENT FIXTURE, NOT A2 AND NOT G2.5',
            'feasibility':'FAIL_INFEASIBLE_WITH_APPROVED_INITIAL_VARPI',
            'solver_status':solved.status,'safe_stop_correct':True,'alpha_v_vmax_rad_s2':pair_limit,
            'abs_Minv_varpi_rad_s2':margin,'violating_joint_indices_1_based':(np.where(margin>pair_limit)[0]+1),
            'reason':'Sum of upper/lower speed rows requires abs(M^-1) varpi <= alpha_v vmax; independent of candidate torque. Point-specific, not an impossibility theorem.',
            'no_gains_or_disturbance_changes':True}

    def make_harness(self,delta,h,tau=None):
        model=IdentityPlant();obs=MomentumObserver(model,self.policy.ko)
        q=np.zeros(7);v=np.linspace(-.02,.02,7);z=obs.initialize(q,v)
        fixed=FixedTorque(np.linspace(-.1,.1,7) if tau is None else tau)
        bounds=DisturbanceBounds(*disturbance_bounds())
        harness=HeldTorqueHarness(model,obs,SlotineLiController(model,self.policy.lambdas,self.policy.kappa),
            synthetic_barrier(model),fixed,ObserverEnvelope(self.policy.ko,bounds.magnitude,bounds.rate),
            MeasuredStateReference(q,v,0.),HoldSchedule(delta,h),dual_harmonic_disturbance)
        return harness,ExecutionState(q,v,z,0.),fixed

    def test_zoh_rk4_stage_times_applied_feedback_and_replan(self):
        harness,state,fixed=self.make_harness(.001,.00025)
        after,log=harness.advance(state)
        self.assertEqual(fixed.calls,1);self.assertEqual(len(log['rk4_stages']),16)
        expected=np.array([j*.00025+k*.00025 for j in range(4) for k in [0,.5,.5,1]])
        self.assertClose([s['t'] for s in log['rk4_stages']],expected,atol=1e-15)
        for stage in log['rk4_stages']:self.assertClose(stage['applied_tau'],fixed.tau)
        oldz,oldt=after.z.copy(),after.t
        replanned=harness.replan_from_measured(after)
        self.assertClose(replanned.z,oldz);self.assertEqual(replanned.t,oldt)
        self.assertClose(harness.reference.sample(oldt).q,replanned.q)
        self.assertClose(harness.reference.sample(oldt).qd,replanned.qd)
        self.assertGreater(log['intervention_Nm'],0)
        after2,log2=harness.advance(replanned)
        self.assertAlmostEqual(log2['rk4_stages'][0]['t'],oldt,places=15)
        self.assertClose(log2['truth_post_run_only'],dual_harmonic_disturbance(after2.t))
        DIAGNOSTICS['held_torque_fixture']=log

    def test_truth_injection_does_not_enter_the_control_update(self):
        one,state,_=self.make_harness(.001,.00025)
        two,_,_=self.make_harness(.001,.00025)
        two._plant_disturbance=lambda t:np.zeros(7)  # test-only plant fixture
        after1,log1=one.advance(state);after2,log2=two.advance(state)
        self.assertClose(log1['u_nom'],log2['u_nom']);self.assertClose(log1['dhat0'],log2['dhat0'])
        self.assertClose(log1['tau_applied'],log2['tau_applied'])
        self.assertGreater(np.linalg.norm(after1.qd-after2.qd),0.)

    def test_solver_failure_requests_stop_and_repeat_solves_are_deterministic(self):
        qp=HardSafetyQP(TAUMAX,self.policy.raw['solver']['QP_settings'])
        with patch('proxsuite.proxqp.dense.QP') as factory:
            backend=factory.return_value
            backend.init.side_effect=RuntimeError('Synthetic solver initialization failure')
            result=qp.solve(np.zeros(7),box_rows())
        self.assertTrue(result.stop_requested);self.assertIsNone(result.applied)
        self.assertEqual(result.status,'SOLVER_ERROR')
        rows=box_rows(-np.eye(7)[0:1],np.ones(1),np.ones(1))
        solved=[qp.solve(np.r_[3.,np.zeros(6)],rows) for _ in range(3)]
        self.assertTrue(all(not x.stop_requested for x in solved))
        for x in solved[1:]:self.assertClose(x.applied,solved[0].applied,atol=1e-12)
        for x in solved:
            raw=np.array(x.diagnostics['raw_slacks'])
            self.assertEqual(x.diagnostics['negative_raw_row_count'],int(np.sum(raw<0)))

    def test_coupled_observer_rk4_against_independent_dhat_ode(self):
        final=[]
        for h in [.01,.005]:
            harness,state,fixed=self.make_harness(.04,h)
            after,_=harness.advance(state)
            final.append((after,harness.observer.estimate(after.q,after.qd,after.z)))
        tau=fixed.tau.copy();v0=np.linspace(-.02,.02,7);ko=np.array(self.policy.ko)
        def independent(t,x):
            disturbance=dual_harmonic_disturbance(t)
            return np.r_[x[7:14],tau+disturbance,ko*(disturbance-x[14:])]
        reference=solve_ivp(independent,(0,.04),np.r_[np.zeros(7),v0,np.zeros(7)],method='DOP853',rtol=1e-12,atol=1e-13)
        self.assertTrue(reference.success)
        errors=[float(np.max(abs(np.r_[s.q,s.qd,dh]-reference.y[:,-1]))) for s,dh in final]
        self.assertLess(errors[1],errors[0]*.15);self.assertLess(errors[1],1e-6)
        DIAGNOSTICS['observer_independent_reference']={'scope':'SYNTHETIC FIXTURE with Delta=.04 s, not policy execution',
            'h_s':[.01,.005],'max_q_v_dhat_errors':errors,'reference':'independent dhat_dot=Ko(d-dhat), DOP853',
            'rtol':1e-12,'atol':1e-13}

    def test_approved_two_factor_grid_is_implemented_as_timing_fixture_only(self):
        rows=[]
        for schedule in self.policy.raw['integration']['validation_grid']:
            dt,h=schedule['control_period_s'],schedule['rk4_step_s']
            harness,state,fixed=self.make_harness(dt,h)
            stage_count=0
            for _ in range(round(.002/dt)):
                state,log=harness.advance(state);stage_count+=len(log['rk4_stages'])
            self.assertAlmostEqual(state.t,.002,places=14)
            self.assertEqual(fixed.calls,round(.002/dt))
            self.assertEqual(stage_count,4*round(.002/h))
            rows.append({'Delta_s':dt,'h_s':h,'controller_updates':fixed.calls,'stage_count':stage_count,'final_q':state.q,'final_qd':state.qd})
        DIAGNOSTICS['two_factor_timing_fixture']={'scope':'SYNTHETIC TIMING UNIT TEST ONLY; not A2 refinement or safety evidence','rows':rows}

    def test_canonical_velocity_cancellation_and_one_sided_allowances(self):
        margin=velocity_margin(5,5*np.ones(7),np.ones(7),np.zeros(7),np.zeros(7),np.zeros(7),np.zeros((7,7)),np.zeros((7,7)))
        self.assertClose(margin,0)
        plus,minus=disturbance_allowances(.2,np.ones(7),2*np.ones(7),.1*np.ones(7),.3*np.ones(7))
        self.assertClose(plus,1.02);self.assertClose(minus,1.02)

    def test_policy_assembly_and_disabled_recovery_do_not_clear_A2(self):
        system=build_components(self.policy);harness,state=system.initialized_fixture()
        self.assertClose(state.q,self.q0)
        self.assertClose(system.observer.estimate(state.q,state.qd,state.z),0)
        self.assertClose(system.bounds.magnitude,.02*TAUMAX)
        self.assertAlmostEqual(system.barriers.w_min,self.wmin)
        self.assertTrue(self.policy.a2_blockers())
        with self.assertRaises(ProtectiveStop):harness.advance(state)

    def test_trace_logger_preserves_negative_samples_and_never_overwrites(self):
        harness,state,_=self.make_harness(.001,.00025)
        _,record=harness.advance(state)
        record['synthetic_negative_slack_fixture']=-1e-12
        logger=TraceLogger({'scope':'SYNTHETIC_LOGGER_TEST'})
        logger.append(record)
        record['synthetic_negative_slack_fixture']=0
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'trace.json';logger.write(path)
            saved=json.loads(path.read_text())
            self.assertEqual(saved['samples'][0]['synthetic_negative_slack_fixture'],-1e-12)
            with self.assertRaises(FileExistsError):logger.write(path)
        with self.assertRaises(ValueError):logger.append({'t0':.005,'t1':.004})


class Results(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.rows=[]
    def startTest(self,test):self.started=time.perf_counter();super().startTest(test)
    def addSuccess(self,test):super().addSuccess(test);self.rows.append({'test':test.id(),'result':'PASS','seconds':time.perf_counter()-self.started})
    def addFailure(self,test,error):super().addFailure(test,error);self.rows.append({'test':test.id(),'result':'FAIL','traceback':self._exc_info_to_string(error,test)})
    def addError(self,test,error):super().addError(test,error);self.rows.append({'test':test.id(),'result':'ERROR','traceback':self._exc_info_to_string(error,test)})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2,resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(Action3Tests))
    args.report.write_text(json.dumps(serial({'scope':'ACTION3_COMPONENT_TESTS_NOT_A2', 'overall_pass':result.wasSuccessful(),
        'tests_run':result.testsRun,'checks':result.rows,'diagnostics':DIAGNOSTICS}),indent=2,allow_nan=False)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
