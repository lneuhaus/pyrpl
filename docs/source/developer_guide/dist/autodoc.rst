How to generate the automatic documentation with Sphinx
**********************************************************

For the automatic documentation to work, please follow the `code style
guidelines for
docstrings <https://github.com/lneuhaus/pyrpl/wiki/Code:-Coding-style-guide#docstrings>`__.
To compile the autodoc with sphinx, simply install sphinx > 1.3
(``pip install sphinx``) and type (starting from the pyrpl root
directory)

::

    cd doc/sphinx
    make html

An extensive discussion of the (automatic) documentation can be found in
issue `#291 <https://github.com/lneuhaus/pyrpl/issues/291>`__.

A few useful links and older information (from issue
`#85 <https://github.com/lneuhaus/pyrpl/issues/85>`__):

-  We should implement this in order to view the autodoc online,
   preferentially by having travis perform a build of the autodoc at
   each commit: https://daler.github.io/sphinxdoc-test/includeme.html
-  The good commands for building autodoc are described here:
   http://gisellezeno.com/tutorials/sphinx-for-python-documentation.html
-  These commands are: ``cd doc/sphinx``
   ``sphinx-apidoc -f -o source/ ../../pyrpl/`` ``make html``

Current version of autodoc:
https://github.com/lneuhaus/pyrpl/blob/master/doc/sphinx/build/html/pyrpl.html
