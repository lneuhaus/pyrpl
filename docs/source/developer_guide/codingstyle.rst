Coding style guidelines
************************

General guidelines
======================

We follow the recommendations from `PEP8 <https://www.python.org/dev/peps/pep-0008/>`_.

Concerning **line length**, we have tried to stick to the 79 characters allowed by PEP8 so far. However, since this definitely restricts the readability of our code, we will accept 119 characters in the future (but please keep this at least consistent within the entire function or class). See the section on `Docstrings`_ below.

Other interesting policies that we should gladly accept are given here.
- `Django style guide <https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/coding-style/>`_


Naming conventions
======================

* Capital letters for each new word in class names, such as `class TestMyClass(object):`.
* Lowercase letters with underscores for functions, such as `def test_my_class():`.
* Any methods or attributes of objects that might be visible in the user API (i.e. which are not themselves hidden) should serve an actual purpose, i.e. `pyrpl.lockbox.lock()`, `pyrpl.rp.iq.bandwidth` and so on.
* Any methods or attributes that are only used internally should be hidden from the API by preceeding the name with an underscore, such as `pyrpl.rp.scope._hidden_attribute` or `pyrpl.spectrum_analyzer._setup_something_for_the_measurement()`.
* Anything that is expected to return immediately and does not require an argument should be a property, asynchronous function calls or one that must pass arguments are implemented as methods.


Docstrings
============

Since we use sphinx for automatic documentation generation, we must ensure
consistency of docstrings among all files in order to generate a nice
documentation:

* follow `PEP257 <https://www.python.org/dev/peps/pep-0257/>`_ and `docstrings in google-style <http://google.github.io/styleguide/pyguide.html?showone=Comments#Comments>`_ --- please read these documents **now**!!!
* keep the maximum width of docstring lines to 79 characters (i.e. 79 characters counted from the first non-whitespace character of the line)
* stay consistent with existing docstrings
* you should make use of the `markup syntax <https://pythonhosted.org/an_example_pypi_project/sphinx.html>`_ allowed by sphinx
* we use `docstrings in google-style <http://google.github.io/styleguide/pyguide.html?showone=Comments#Comments>`_, together with the `sphinx-extension napoleon <http://www.sphinx-doc.org/en/stable/ext/napoleon.html>`_ to format them as nice as the `harder-to-read (in the source code) sphinx docstrings <https://pythonhosted.org/an_example_pypi_project/sphinx.html#function-definitions>`_
* the guidelines are summarized in the `napoleon/sphinx documentation example <http://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html#example-google>`_ or in the example below::

      class SoundScope(Module):
          """
          An oscilloscope that converts measured data into sound.

          The oscilloscope works by acquiring the data from the redpitaya scope
          implemented in pyrpl/fpga/rtl/red_pitaya_scope_block.v, subsequent
          conversion through the commonly-known `Kolmogorov-Audio algorithm
          <http://www.wikipedia.org/Kolmogorov>`_ and finally outputting sound
          with the python package "PyAudio".

          Methods:
              play_sound: start sending data to speaker
              stop: stop the sound output

          Attributes:
              volume (float): Current volume
              channel (int): Current channel
              current_state (str): One of ``current_state_options``
              current_state_options (list of str): ['playing', 'stopped']
          """

          def play_sound(self, channel, lowpass=True, volume=0.5):
              """
              Start sending data of a scope channel to a speaker.

              Args:
                  channel (int): Scope channel to use as data input
                  lowpass (bool, optional): Turns on a 10 kHz lowpass
                      filter before data sent to the output. Defaults to True.
                  volume (float, optional): volume for sound output.
                      Defaults to 0.5.

              Returns:
                  bool: True for success, False otherwise.

              Raises:
                  NotImplementedError: The given channel is not available.
                  CannotHearAnythingException: Selected volume is too loud.
              """
