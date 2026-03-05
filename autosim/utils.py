"""
utils.py stub — MEEP 내부 테스트 유틸 (autosim 실행 호환용)
"""
import unittest
import numpy as np

class ApproxComparisonTestCase(unittest.TestCase):
    """MEEP 테스트용 근사 비교 기반 클래스 stub"""
    decimal = 5
    
    def assertClose(self, a, b, decimal=None):
        d = decimal or self.decimal
        np.testing.assert_almost_equal(a, b, decimal=d)
    
    def assertAlmostEqual(self, a, b, places=5, msg=None, delta=None):
        super().assertAlmostEqual(a, b, places=places, msg=msg, delta=delta)
