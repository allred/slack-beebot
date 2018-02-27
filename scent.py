#!/usr/bin/env python
# config file for 'sniffer' 
from sniffer.api import *
import os
import subprocess
import termstyle

pass_fg_color = termstyle.green
pass_bg_color = termstyle.bg_default
fail_fg_color = termstyle.red
fail_bg_color = termstyle.bg_default

watch_paths = ['.']

@file_validator
def py_files(filename):
    return filename.endswith('.py') and not os.path.basename(filename).startswith('.')

@runnable
def python_tests(*args):
    import unittest
    tests = unittest.TestLoader().discover('.', 'test*.py')
    #import pdb; pdb.set_trace()
    result = unittest.TextTestRunner().run(tests)
    return result.wasSuccessful()

#@runnable
#def python_tests(*args):
#    command = "test.py"
#    return subprocess.run(command, shell=True).returncode == 0

#@runnable
#def execute_nose(*args):
#    import nose
#    return nose.run(argv=list(args))
