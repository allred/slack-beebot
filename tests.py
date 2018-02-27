#!/usr/bin/env python
import beebot
import re
import sys
import unittest

class TestBeebot(unittest.TestCase):
    def setUp(self):
        self.b = beebot.Beebot()

    def test_help_message(self):
        self.assertTrue(re.search('Options', self.b.help_message()))

if __name__ == '__main__':
    unittest.main()
