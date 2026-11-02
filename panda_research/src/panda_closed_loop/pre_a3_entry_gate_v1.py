"""Technical fail-closed planner entry gate, without administrative requests."""
from .m1_margins_v1 import exact_initial_pair_obstruction

class PlannerEntryBlocked(RuntimeError):
    def __init__(self,reason,evidence):
        self.reason=reason;self.evidence=evidence
        super().__init__('Planner entry NO-GO: '+reason)

def require_planner_entry(system,measured_record,registry):
    # This certificate is freshly computed from the ACTUAL supplied state and
    # its propagated bound. It is not a stored witness or a controller fallback.
    witness=exact_initial_pair_obstruction(system,measured_record)
    if witness['status']=='NO_GO_NECESSARY_START_PAIRS':
        raise PlannerEntryBlocked('FULL_INITIAL_SPEED_PAIR_CONSTRAINTS_INFEASIBLE',witness)
    try:registry.require_certified()
    except ValueError as error:
        raise PlannerEntryBlocked('COMMON_DOMAIN_BOUNDS_NOT_QUALIFIED',{'reason':str(error)}) from error
    return {'entry_necessary_pairs_pass':True,'scope':'Entry only; all other Stage1/continuous-time/A3 gates still required'}
