"""Technical fail-closed planner entry gate, without administrative requests."""
from .m1_margins_v1 import exact_initial_pair_obstruction

class PlannerEntryBlocked(RuntimeError):
    def __init__(self,reason,evidence):
        self.reason=reason;self.evidence=evidence
        super().__init__('Planner entry NO-GO: '+reason)

def require_planner_entry(system,measured_record,registry,require_certified=False):
    # This certificate is freshly computed from the ACTUAL supplied state and
    # its propagated bound. It is not a stored witness or a controller fallback.
    witness=exact_initial_pair_obstruction(system,measured_record)
    if witness['status']=='NO_GO_NECESSARY_START_PAIRS':
        raise PlannerEntryBlocked('FULL_INITIAL_SPEED_PAIR_CONSTRAINTS_INFEASIBLE',witness)
    # Numerical qualification and certified-bound qualification are separate.
    # The current registry fails even its finite held-out checks; Level1 is
    # not silently introduced as a prerequisite for numerical diagnostics.
    document=registry.document;audit=document.get('heldout_exceedances',{})
    upper=[n for n in registry.values if n!='m1']
    if (document.get('heldout_points',0)<=0 or any(n not in audit or audit[n]['component_count']!=0 for n in upper)):
        raise PlannerEntryBlocked('COMMON_DOMAIN_NUMERICAL_BOUND_AUDIT_FAILED',{'heldout_exceedances':audit})
    if require_certified:
        try:registry.require_certified()
        except ValueError as error:
            raise PlannerEntryBlocked('CERTIFIED_DOMAIN_BOUNDS_UNAVAILABLE',{'reason':str(error)}) from error
    return {'entry_necessary_pairs_pass':True,'finite_numerical_bound_audit_pass':True,'certified':False,
            'scope':'Entry and finite audit only; all other Stage1/continuous-time/A3 gates still required. No Level1 claim.'}
