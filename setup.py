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
      packages=['pyrpl'],
      package_dir={'pyrpl': ''},
      package_data={'pyrpl':['fpga/red_pitaya.bin',
                                'monitor_server/monitor_server']},
      requires=["paramiko","scp"]
      )
