###############################################################################
#    pyrpl - DSP servo controller for quantum optics with the RedPitaya
#    Copyright (C) 2014-2016  Leonhard Neuhaus  (neuhaus@spectro.jussieu.fr)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################

from . import monitor_client
from . import hardware_modules as rp
from .sshshell import SSHshell
from .pyrpl_utils import get_unique_name_list_from_class_list

import logging
import os
import random
import socket
from time import sleep
import numpy as np

from paramiko import SSHException
from scp import SCPClient, SCPException
from collections import OrderedDict


class DummyMemoryTree(dict):
    """
    This class is there to emulate a MemoryTree, for users who would use RedPitaya object without Pyrpl object
    """
    @property
    def _keys(self):
        return self.keys

    def __getattribute__(self, item):
        try:
            attr = super(DummyMemoryTree, self).__getattribute__(item)
            return attr
        except AttributeError:
            return self[item]

class RedPitaya(SSHshell):
    _binfilename = 'fpga.bin'
    """
    module_dict = OrderedDict([ ('hk', rp.HK), # careful: the initialization OrderedDict(a=x, b=y) looses the order
                                ('ams', rp.AMS),
                                ('scope', rp.Scope),
                                ('sampler', rp.Sampler),
                                ('asg1', rp.Asg1),
                                ('asg2', rp.Asg2),
                                ('pwm', (rp.AuxOutput, 2)), # dict key is (cls, number of instances)
                                ('iq', (rp.IQ, 3)),
                                ('pid', (rp.Pid, 4)),
                                ('iir', rp.IIR)])# redpitaya modules are automatically generated from this dict
    """
    cls_modules = [rp.HK, rp.AMS, rp.Scope, rp.Sampler, rp.Asg1, rp.Asg2] + \
                  [rp.AuxOutput]*2 + [rp.IQ]*3 + [rp.Pid]*4 + [rp.IIR]

    def __init__(self, hostname='192.168.1.100', port=2222,
                 user='root', password='root',
                 delay=0.05, 
                 autostart=True, reloadfpga=True, reloadserver=False, 
                 filename=None, dirname=None,
                 leds_off=True, frequency_correction=1.0, timeout = 3,
                 monitor_server_name='monitor_server',
                 silence_env = False, config=DummyMemoryTree() # In general, config is the parent's memoryTree
                 ):
        """installs and starts the interface on the RedPitaya at hostname that allows remote control

        if you are experiencing problems, try to increase delay, or try logging.getLogger().setLevel(logging.DEBUG)"""
        self.logger = logging.getLogger(name=__name__)
        #self.license()
        self._slaves = []
        self.serverdirname = "//opt//pyrpl//"
        self.serverrunning = False
        self.hostname = hostname
        self.user = user
        self.password = password
        self.delay = delay
        self.port = port
        self.defaultport = port # sometimes we randomly pick another port to bypass problems of the linux on redpitaya
        self.conn = None
        self.client = None
        self.frequency_correction = frequency_correction
        self.leds_off = leds_off
        self.timeout = timeout
        self.monitor_server_name = monitor_server_name
        self.c = config
        self.modules = OrderedDict()

        # get parameters from os.environment variables
        if not silence_env:
            for k in ["hostname",
                      "port",
                      "user",
                      "password",
                      "delay",
                      "timeout",
                      "monitor_server_name"]:
                if "REDPITAYA_"+k.upper() in os.environ:
                    newvalue = os.environ["REDPITAYA_"+k.upper()]
                    oldvalue = self.__getattribute__(k)
                    self.__setattr__(k, type(oldvalue)(newvalue))
                    if k == "password": # do not show the password on the screen
                        newvalue = "********"
                    self.logger.warning("Variable %s with value %s overwritten by "
                                        +"environment variable REDPITAYA_%s with "
                                        +"value %s", k, oldvalue,
                                        k.upper(), newvalue)
        # check filenames - should work without specifying them
        if filename is None:
            self.filename = 'fpga//red_pitaya.bin'
        else:
            self.filename = filename
        if dirname is None:
            self.dirname = os.path.abspath(os.path.dirname(rp.__file__)) #or inspect.getfile(rp)
        else:
            self.dirname = dirname
        if not os.path.exists(self.dirname):
            if os.path.exists(os.path.abspath(os.path.join(self.dirname,'prypl'))):
                self.dirname = os.path.abspath(os.path.join(self.dirname,'prypl'))
            else:
                raise IOError("Wrong dirname",
                          "The directory of the pyrl package could not be found. Please try again calling RedPitaya"
                          "with the additional argument dirname='c://github//pyrpl//pyrpl' adapted to your installation"
                          " directory of pyrpl! Current dirname: "
                           +self.dirname)
        if self.hostname == "unavailable": # simulation mode - start without connecting
            self.logger.warning("Starting client in dummy mode...")
            self.startdummyclient()
            return
        # start ssh connection
        super(RedPitaya, self).__init__(hostname=self.hostname, 
                                        user=self.user,
                                        password=self.password, 
                                        delay = self.delay, 
                                        timeout = self.timeout)
        # test ssh connection for exceptions
        try:
            self.ask()
        except socket.error:
                # try again before anything else
                super(RedPitaya, self).__init__(hostname=self.hostname, 
                                                user=self.user,
                                                password=self.password,
                                                delay=self.delay, 
                                                timeout = self.timeout)
        # start other stuff
        if reloadfpga:
            self.update_fpga()
        if reloadserver:
            self.installserver()
        if autostart:
            self.start()

    def switch_led(self, gpiopin=0, state=False):
        self.ask("echo " + str(gpiopin) + " > /sys/class/gpio/export")
        sleep(self.delay)
        self.ask(
            "echo out > /sys/class/gpio/gpio" +
            str(gpiopin) +
            "/direction")
        sleep(self.delay)
        if state:
            state = "1"
        else:
            state = "0"
        self.ask( "echo " + state + " > /sys/class/gpio/gpio" +
            str(gpiopin) + "/value")
        sleep(self.delay)

    def update_fpga(self, filename=None):
        if filename is None:
            filename = self.filename
        self.end()
        sleep(self.delay)
        self.ask('rw')
        sleep(self.delay)
        self.ask('mkdir ' + self.serverdirname)
        sleep(self.delay)
        source = os.path.join(self.dirname,filename)
        if not os.path.isfile(source):
            source = os.path.join(self.dirname,'fpga', filename)
        if not os.path.isfile(source):
            raise IOError("Wrong filename",
              "The fpga bitfile was not found at the expected location. Try passing the arguments "
              "dirname=\"c://github//pyrpl//pyrpl//\" adapted to your installation directory of pyrpl "
              "and filename=\"red_pitaya.bin\"! Current dirname: "
              +self.dirname
              +" current filename: "+self.filename)
        try:
            self.scp.put(source,
                         os.path.join(self.serverdirname,self._binfilename))
        except (SCPException, SSHException):
            # try again before failing
            self.startscp()
            sleep(self.delay)
            self.scp = SCPClient(self.ssh.get_transport())
        sleep(self.delay)
        # kill all other servers to prevent reading while fpga is flashed
        self.end()
        self.ask('killall nginx')
        self.ask('systemctl stop redpitaya_nginx') # for 0.94 and higher
        self.ask('cat ' 
                 + os.path.join(self.serverdirname, self._binfilename)
                 + ' > //dev//xdevcfg')
        sleep(self.delay)
        self.ask('rm -f '+ os.path.join(self.serverdirname, self._binfilename))
        self.ask("nginx -p //opt//www//")
        self.ask('systemctl start redpitaya_nginx') # for 0.94 and higher #needs test
        sleep(self.delay)
        self.ask('ro')

    def fpgarecentlyflashed(self):
        self.ask()
        result =self.ask("echo $(($(date +%s) - $(date +%s -r \""
        + os.path.join(self.serverdirname, self._binfilename) +"\")))")
        age = None
        for line in result.split('\n'):
            try:
                age = int(line.strip())
            except:
                pass
            else:
                break
        if not age:
            self.logger.debug("Could not retrieve bitfile age from: %s",
                            result)
            return False
        elif age > 10:
            self.logger.debug("Found expired bitfile. Age: %s", age)
            return False
        else:
            self.logger.debug("Found recent bitfile. Age: %s", age)
            return True

    def installserver(self):
        self.endserver()
        sleep(self.delay)
        self.ask('rw')
        sleep(self.delay)
        self.ask('mkdir ' + self.serverdirname)
        sleep(self.delay)
        self.ask("cd " + self.serverdirname)
        #try both versions
        for serverfile in ['monitor_server','monitor_server_0.95']:
            sleep(self.delay)
            try:
                self.scp.put(
                    os.path.join(self.dirname, 'monitor_server', serverfile),
                    self.serverdirname+self.monitor_server_name)
            except (SCPException, SSHException):
                self.logger.exception("Upload error. Try again after rebooting your RedPitaya..")
            sleep(self.delay)
            self.ask('chmod 755 ./'+self.monitor_server_name)
            sleep(self.delay)
            self.ask('ro')
            result = self.ask("./"+self.monitor_server_name+" "+ str(self.port))
            sleep(self.delay)
            result += self.ask()
            if not "sh" in result: 
                self.logger.info("Server application started on port %d",self.port)
                return self.port
            else: # means we tried the wrong binary version. make sure server is not running and try again with next file
                self.endserver()
        
        #try once more on a different port
        if self.port == self.defaultport:
            self.port = random.randint(self.defaultport,50000)
            self.logger.warning("Problems to start the server application. Trying again with a different port number %d",self.port)
            return self.installserver()
        
        self.logger.error("Server application could not be started. Try to recompile monitor_server on your RedPitaya (see manual). ")
        return None
    
    def startserver(self):
        self.endserver()
        sleep(self.delay)
        if self.fpgarecentlyflashed():
            self.logger.info("FPGA is being flashed. Please wait for 2 seconds.")
            sleep(2.0)
        result = self.ask(self.serverdirname+"/"+self.monitor_server_name
                          +" "+ str(self.port))
        if not "sh" in result: # sh in result means we tried the wrong binary version
            self.logger.info("Server application started on port %d",self.port)
            self.serverrunning = True
            return self.port
        #something went wrong
        return self.installserver()
    
    def endserver(self):
        try:
            self.ask('\x03') #exit running server application
        except:
            self.logger.exception("Server not responding...")
        if 'pitaya' in self.ask():
            self.logger.info('>') # formerly 'console ready'
        sleep(self.delay)
        # make sure no other monitor_server blocks the port
        self.ask('killall ' + self.monitor_server_name)
        self.serverrunning = False
        
    def endclient(self):
        del self.client
        self.client = None

    def start(self):
        if self.leds_off:
            self.switch_led(gpiopin=0, state=False)
            self.switch_led(gpiopin=7, state=False)
        self.startserver()
        sleep(self.delay)
        self.startclient()

    def end(self):
        self.endserver()
        self.endclient()
    """
    def __del__(self):
        self.end()
        try:
            self.ssh.close()
        except socket.error:
            self.logger.warning("__del__ tried to close a socket that "
                                "already was closed. ")
        super(RedPitaya, self).__del__()
    """

    def restart(self):
        self.end()
        self.start()

    def restartserver(self, port=None):
        """restart the server. usually executed when client encounters an error"""
        if port is not None:
            if port < 0: #code to try a random port
                self.port = random.randint(2223,50000)
            else:
                self.port = port
        return self.startserver()

    def license(self):
        self.logger.info("""\r\n    pyrpl  Copyright (C) 2014-2016  Leonhard Neuhaus
    This program comes with ABSOLUTELY NO WARRANTY; for details read the file
    "LICENSE" in the source directory. This is free software, and you are
    welcome to redistribute it under certain conditions; read the file
    "LICENSE" in the source directory for details.\r\n""")

    def startclient(self):
        self.client = monitor_client.MonitorClient(
            self.hostname, self.port, restartserver=self.restartserver)
        self.makemodules()
        self.logger.info("Client started with success")

    def startdummyclient(self):
        self.client = monitor_client.DummyClient()
        self.makemodules()
        self.logger.warning("Dummy mode started...")

    def makemodule(self, name, cls):
        module = cls(self.client, name=name, parent=self)
        setattr(self, name, module)
        self.modules[name] = module

    def makemodules(self):
        """
        Automatically generates modules from the list RedPitaya.cls_modules
        """
        """
        for name, cls in self.module_dict.items():
            if np.iterable(cls): # dict key is (cls, number of instances)
                cls, num = cls
                for index in range(num):
                    self.makemodule(name + str(index + 1), cls) # module have 1-based indices
            else:
                self.makemodule(name, cls)
        """
        names = get_unique_name_list_from_class_list(self.cls_modules)
        for cls, name in zip(self.cls_modules, names):
            self.makemodule(name, cls)

        """
        self.hk = rp.HK(self.client, parent=self)
        self.ams = rp.AMS(self.client, parent=self)
        self.scope = rp.Scope(self.client, parent=self)
        self.sampler = rp.Sampler(self.client, parent=self)
        self.asg1 = rp.Asg1(self.client, parent=self)
        self.asg2 = rp.Asg2(self.client, parent=self)
        self.pwm0 = rp.AuxOutput(self.client, output='pwm0', parent=self)
        self.pwm1 = rp.AuxOutput(self.client, output='pwm1', parent=self)
        for name, module, number in [("pid", rp.Pid, 4),
                                     ("iir", rp.IIR, 1),
                                     ("iq", rp.IQ, 2)]:
            # make a list for each kind of module
            thislist = []
            self.__setattr__(name+'s', thislist)
            # fill it with the modules
            for i in range(number):
                if number > 1:
                    thisname = name + str(i)
                else:
                    thisname = name
                thismodule = module(self.client, module=thisname, parent=self)
                thislist.append(thismodule)
                # to be deprecated
                self.__setattr__(thisname, thismodule)
        # iq2 is special: two outputs for scope/specAn. This special treatment
        # should soon be made more general. For thsi reason, we already
        # exclude it from the iqs list, such that it cannot be popped away..
        self.iq2 = rp.IQ(self.client, module='iq2', parent=self)
        # higher functionality modules
        #self.na = NetworkAnalyzer(self)
        #self.spec_an = SpectrumAnalyzer(self)
        """

    def make_a_slave(self, port=None, monitor_server_name=None, gui=False):
        if port is None:
            port = self.port + len(self._slaves)*10 + 1
        if monitor_server_name is None:
            monitor_server_name = self.monitor_server_name + str(port)
        r = RedPitaya(hostname=self.hostname,
                         port=port,
                         user=self.user,
                         password=self.password,
                         delay=self.delay,
                         autostart=True,
                         reloadfpga=False,
                         reloadserver=False,
                         filename=self.filename,
                         dirname=self.dirname,
                         leds_off=self.leds_off,
                         frequency_correction=self.frequency_correction,
                         timeout=self.timeout,
                         monitor_server_name=monitor_server_name,
                         silence_env=True,
                         ) #gui=gui)
        r._master = self
        self._slaves.append(r)
        return r
