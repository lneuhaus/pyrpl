#note to the developer
#do not forget to make source distribution with
#python setup.py sdist

from distutils.core import setup
setup(name='pyrpl',
      version='0.9.0.0',
      description='DSP servo controller for quantum optics with the RedPitaya',
      author='Leonhard Neuhaus',
      author_email='neuhaus@spectro.jussieu.fr',
      url='https://www.github.com/lneuhaus/pyrplockbox/',
      license='GPLv3',
      classifiers= ['Programming Language :: Python :: 2.7',
                    'Development Status :: 4 - Beta',
                    'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
                    'Topic :: Scientific/Engineering :: Human Machine Interfaces',
                    'Topic :: Scientific/Engineering :: Physics',
                    'Programming Language :: C'],
      keywords='RedPitaya DSP FPGA IIR PDH synchronous detection filter PID control lockbox servo feedback lock quantum optics',
      packages=['pyrpl'],
      package_dir={'pyrpl': ''},
      package_data={'pyrpl':['fpga/red_pitaya.bin',
                            'monitor_server/monitor_server']},
      requires=["paramiko","scp"]
      )
