#note to the developer
#do not forget to make source distribution with
#python setup.py sdist

#much of the code here is from
#https://jeffknupp.com/blog/2013/08/16/open-sourcing-a-python-project-the-right-way/

#! /usr/bin/env python
from __future__ import print_function
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import io
import codecs
import os
import sys

here = os.path.abspath(os.path.dirname(__file__))
def read(*filenames, **kwargs):
    encoding = kwargs.get('encoding', 'utf-8')
    sep = kwargs.get('sep', '\n')
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)

long_description = read('README.md') #, 'CHANGES.txt')

class PyTest(TestCommand):
    #user_options = [('pytest-args=', 'a', "192.168.1.100")] #not yet working
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True
    def run_tests(self):
        import pytest
        errcode = pytest.main(self.test_args)
        sys.exit(errcode)
        
from distutils.core import setup
setup(name='pyrpl',
      version='0.9.0.0',
      description='DSP servo controller for quantum optics with the RedPitaya',
      long_description = long_description,
      author='Leonhard Neuhaus',
      author_email='neuhaus@spectro.jussieu.fr',
      url='https://www.github.com/lneuhaus/pyrplockbox/',
      license='GPLv3',
      classifiers= ['Programming Language :: Python :: 2.7',
                    'Natural Language :: English',
                    'Development Status :: 4 - Beta',
                    'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
                    'Topic :: Scientific/Engineering :: Human Machine Interfaces',
                    'Topic :: Scientific/Engineering :: Physics',
                    'Programming Language :: C'],
      keywords='RedPitaya DSP FPGA IIR PDH synchronous detection filter PID control lockbox servo feedback lock quantum optics',
      packages=['pyrpl'],
      #package_dir={'pyrpl': ''},
      package_data={'pyrpl':['fpga/red_pitaya.bin',
                            'monitor_server/monitor_server']},
      install_requires=["paramiko","scp","matplotlib","numpy"],
      setup_requires=["paramiko","scp","matplotlib","numpy"],
      platforms='any',

      #stuff for unitary test with pytest
      tests_require=['pytest'],
      extras_require={'testing': ['pytest']},
      cmdclass={'test': PyTest},
      )
