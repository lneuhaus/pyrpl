#unitary test for the redpitaya module

import unittest

class RedPitayaTestCase(unittest.TestCase):
    def setUp(self):
        pass
        
    def tearDown(self):
        #del r
        pass
		
    def test_imports(self):
        import pyrpl
        from pyrpl import RedPitaya
        from pyrpl import Pyrpl
        
    def test_2(self):
        self.assertEqual(2, 2,
                         '2 isnt equal to itself!')
