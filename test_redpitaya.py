#unitary test for the redpitaya module

import unittest

class RedPitayaTestCase(unittest.TestCase):
    def setUp(self):
        pass
        
    def tearDown(self):
        #del r
        pass
		
    def test_1(self):
        import pyrplockbox.redpitaya
        self.assertEqual(1, 1,
                         '1 isnt equal to itself!')
    def test_2(self):
        self.assertEqual(2, 2,
                         '2 isnt equal to itself!')
