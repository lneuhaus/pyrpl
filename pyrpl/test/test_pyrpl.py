# unitary test for the pyrpl module

import unittest
import os


class RedPitayaTestCases(unittest.TestCase):

    def setUp(self):
        self.hostname = os.environ.get('REDPITAYA')

    def tearDown(self):
        pass

    def test_import(self):
        import pyrpl
        self.assertEqual(2, 2, 'This one definitely works')
