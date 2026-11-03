"""Cross-diagonal time matching regression, independent of energy values."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import unittest
import numpy as np
from panda_closed_loop.active_sampled_clock_v1 import common_energy_indices

class ClockTests(unittest.TestCase):
    def test_both_cross_diagonal_directions(self):
        x=np.arange(1,9)*.125;y=np.arange(1,5)*.25
        for a,b in [(x,y),(y,x)]:
            i,j=common_energy_indices(a,b)
            np.testing.assert_array_equal(a[i],b[j])
            np.testing.assert_array_equal(a[i],[.25,.5,.75,1.])
    def test_same_clock(self):
        x=np.arange(1,5)*.25;i,j=common_energy_indices(x,x)
        np.testing.assert_array_equal(i,j);self.assertEqual(len(i),4)
    def test_irregular_and_mismatched_horizon_rejected(self):
        with self.assertRaises(ValueError):common_energy_indices([.1,.2,.31,.4],[.2,.4])
        with self.assertRaises(ValueError):common_energy_indices([.1,.2,.3],[.2,.4])

if __name__=='__main__':unittest.main(verbosity=2)
