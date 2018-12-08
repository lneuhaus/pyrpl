#!/usr/bin/env python
"""
simple example script for running and testing notebooks.
Usage: `ipnbdoctest.py foo.ipynb [bar.ipynb [...]]`
"""
# License: Public Domain, but credit is nice (Min RK).

    
from glob import glob
import os
import sys

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
from nbconvert.preprocessors.execute import CellExecutionError

NOTEBOOK_DIR = os.path.dirname(__file__)

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
    ep = ExecutePreprocessor(kernel_name=kernel_name, timeout=10) #, allow_errors=True

    try:
      ep.preprocess(nb, {'metadata': {'path': NOTEBOOK_DIR}})

    except CellExecutionError as e: 
      if "SKIP" in e.traceback:
        print(str(e.traceback).split("\n")[-2])
      else:
        raise e

  return nb, errors

for notebook in glob(NOTEBOOK_DIR + "/*.ipynb"):
    nb, errors = _notebook_run(notebook)
    assert errors == []
    # Make sure the kernel is running the current python version...
    assert nb['cells'][0]['outputs'][0]['text'].rstrip('\n')==sys.version
    
