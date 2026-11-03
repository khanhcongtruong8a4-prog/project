from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import unittest,numpy as np
from panda_closed_loop.slack_audit_v2_4b import consistent_slacks
class Contracts(unittest.TestCase):
    def test_one_ulp_large_positive_identity(self):
        C=np.zeros((1,28));b=np.array([2377.6314952251495]);x=np.zeros(28)
        raw=1e-8+b;stored=np.nextafter(raw,-np.inf)
        self.assertTrue(consistent_slacks(C,b,x,stored)[0])
        self.assertGreater(abs(raw-stored)[0],1e-13)
    def test_corrupted_positive_value_rejected(self):
        C=np.zeros((1,28));b=np.array([2377.6314952251495]);x=np.zeros(28)
        self.assertFalse(consistent_slacks(C,b,x,1e-8+b+.001)[0])
    def test_negative_sign_never_waived(self):
        C=np.zeros((1,28));b=np.array([-1.000001e-8]);x=np.zeros(28)
        self.assertFalse(consistent_slacks(C,b,x,1e-8+b)[0])
if __name__=='__main__':unittest.main(verbosity=2)
