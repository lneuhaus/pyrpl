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


NOTEBOOK_DIR = os.path.dirname(__file__)
TUTORIAL_DIR = os.path.join(os.path.dirname(
    os.path.dirname(os.path.dirname(
               NOTEBOOK_DIR))), "docs", "example-notebooks")

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

def _notebook_run(path):
    """
    Execute a notebook via nbconvert and collect output.
    :returns (parsed nb object, execution errors)
    """
    kernel_name = 'python%d' % sys.version_info[0]
    errors = []


    with open(path) as f:
        nb = nbformat.read(f, as_version=4)
        nb.metadata.get('kernelspec', {})['name'] = kernel_name
        ep = MyExecutePreprocessor(kernel_name=kernel_name, timeout=65) #,
        # allow_errors=True
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

# For some reason, the notebook preprocessor doesn't close
# itself properly in python 3.7. I don't think it's worth the effort
# to fix this, we just hope that unittesting notebooks in python 3.8 is
# sufficient...
if sys.version>'3.8':
    for notebook in glob(NOTEBOOK_DIR + "/*.ipynb") + glob(TUTORIAL_DIR +
                                                             '/*.ipynb'):
        print("testing ", notebook)
        nb, errors = _notebook_run(notebook)
        assert errors == []
        # Make sure the kernel is running the current python version...
        #assert nb['cells'][0]['outputs'][0]['text'].rstrip('\n')==sys.version
        print("Finished testing notebook: %s"%notebook)
        sys.stdout.flush()
