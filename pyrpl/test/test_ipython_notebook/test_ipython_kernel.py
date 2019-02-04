#!/usr/bin/env python
"""
simple example script for running and testing notebooks.
Usage: `ipnbdoctest.py foo.ipynb [bar.ipynb [...]]`
"""
# License: Public Domain, but credit is nice (Min RK).

    
from glob import glob
import os
import sys
from ...redpitaya import defaultparameters
import os
import io

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
from nbconvert.preprocessors.execute import CellExecutionError


try:
    TimeoutError # builtin in python 3
except NameError:
    TimeoutError = RuntimeError # a RunTimeError is launched in python 2.7


class MyExecutePreprocessor(ExecutePreprocessor):
    def preprocess_cell(self, cell, resources, cell_index):
        if cell.source.startswith("#no-test"):
            return cell, resources
        if cell.source.startswith("#define hostname"):
            # replace hostname by unittest hostname
            for key in ['hostname', 'user', 'password']:
                #if defaultparameters[key] is not None:
                #    cell.source += '\n%s = "%s"'%(key.upper(), defaultparameters[key])
                envvarname = 'REDPITAYA_%s'%(key.upper())
                if envvarname in os.environ:
                    cell.source += '\n%s = "%s"'%(key.upper(), os.environ[envvarname])
        return super(MyExecutePreprocessor, self).preprocess_cell(cell,\
                resources, cell_index)


NOTEBOOK_DIR = os.path.dirname(__file__)
TUTORIAL_DIR = os.path.abspath(
    os.path.join(NOTEBOOK_DIR, os.pardir, os.pardir, os.pardir, "docs", "example-notebooks"))


def _notebook_run(path):
  """
  Execute a notebook via nbconvert and collect output.
   :returns (parsed nb object, execution errors)
  """
  kernel_name = 'python%d' % sys.version_info[0]
  errors = []
  with io.open(path, mode='r', encoding='UTF-8') as f:
    nb = nbformat.read(f, as_version=4)
    nb.metadata.get('kernelspec', {})['name'] = kernel_name
    ep = MyExecutePreprocessor(kernel_name=kernel_name, timeout=65)
    #,# allow_errors=True
    #ep.start_new_kernel()
    try:
        ep.preprocess(nb, resources={'metadata': {'path': NOTEBOOK_DIR}})
    except (CellExecutionError, TimeoutError) as e:
      if hasattr(e, 'traceback') and "SKIP" in e.traceback:
            print(str(e.traceback).split("\n")[-2])
      else:
        raise e
  return nb, errors

##### commented out stuff below because changing defaultparameters might lead
# to unexpected behavior ####################################################
# If redpitaya was selected from a list, adds it as an environment variable
# for the notebook to retieve it
#for key in ['hostname', 'user', 'password']:
#    envvarname = 'REDPITAYA_%s'%(key.upper())
#    if not envvarname in os.environ:
#        os.environ[envvarname] = defaultparameters[key]
##############################################################################

# testing for the transferability of environment variables
os.environ["python_sys_version"] = sys.version

exceptions = ['async_acquisition.ipynb',  # fails in python-37
              'tutorial.ipynb'  # fails in python-36
              ]

# iterate through all notebooks and run tests
for notebook in \
        (glob(NOTEBOOK_DIR+"/*.ipynb") + glob(TUTORIAL_DIR+'/*.ipynb')):
    for exception in exceptions:
        _, filename = os.path.split(notebook)
        if filename in exceptions:
            print("Skipping notebook: %s" % notebook)
            sys.stdout.flush()
            break
    else:
        print("Testing notebook: %s"%notebook)
        sys.stdout.flush()
        nb, errors = _notebook_run(notebook)
        assert errors == []
        # Make sure the kernel is running the current python version...
        #assert nb['cells'][0]['outputs'][0]['text'].rstrip('\n')==sys.version
        print("Finished testing notebook: %s"%notebook)
        sys.stdout.flush()



