# unitary test for the pyrpl module

import unittest
import os
import logging
logger = logging.getLogger(name=__name__)


class RedPitayaTestCases(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_import(self):
        import pyrpl
        self.assertEqual(2, 2, 'This one definitely works')
