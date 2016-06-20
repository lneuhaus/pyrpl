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

import os
from time import sleep
import time
import socket
import math
import numpy as np
import inspect
import random
import logging

from scp import SCPException
from paramiko import SSHException

from .sshshell import SSHshell
from . import monitor_client
from . import redpitaya_modules as rp

class RedPitaya(SSHshell):
    def __init__(self, hostname='192.168.1.100', port=2222,
                 user='root', password='root',
                 delay=0.05, 
                 autostart=True, reloadfpga=True, reloadserver=False, 
                 filename=None, dirname=None,
                 leds_off=True, frequency_correction=1.0, timeout = 3
                 ):
        """installs and starts the interface on the RedPitaya at hostname that allows remote control
        
        if you are experiencing problems, try to increase delay, or try logging.getLogger().setLevel(logging.DEBUG)"""
        self.logger = logging.getLogger(name=__name__)
        #self.license()
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
        # get parameters from os.environment variables
        for k in ["hostname","port","user","password","delay", "timeout"]:
            if "REDPITAYA_"+k.upper() in os.environ:
                newvalue = os.environ["REDPITAYA_"+k.upper()]
                self.logger.warning("Variable %s with value %s overwritten by "
                                    +"environment variable REDPITAYA_%s with "
                                    +"value %s", k, self.__getattribute__(k),
                                    k.upper(), newvalue) 
                self.__setattr__(k, newvalue) 
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
            if os.path.exists(ps.path.abspath(os.path.join(self.dirname,'prypl'))):
                self.dirname = ps.path.abspath(os.path.join(self.dirname,'prypl'))
            else:
                raise IOError("Wrong dirname",
                          "The directory of the pyrl package could not be found. Please try again calling RedPitaya with the additional argument dirname='c://github//pyrpl//pyrpl' adapted to your installation directory of pyrpl! Current dirname: "
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
            source = os.path.join(self.dirname,'fpga',filename)
        if not os.path.isfile(source):
            raise IOError("Wrong filename",
              "The fpga bitfile was not found at the expected location. Try passing the arguments dirname=\"c://github//pyrpl//pyrpl//\" adapted to your installation directory of pyrpl and filename=\"red_pitaya.bin\"! Current dirname: "
              +self.dirname
              +" current filename: "+self.filename)
        try:
            self.scp.put(source, self.serverdirname)
        except (SCPException, SSHException):
            # try again before failing
            self.startscp()
            sleep(self.delay)
            self.scp = SCPClient(self.ssh.get_transport())
        sleep(self.delay)
        self.ask('killall nginx')
        self.ask('systemctl stop redpitaya_nginx') # for 0.94 and higher
        self.ask('cat ' 
                 + os.path.join(self.serverdirname, os.path.basename(filename)) 
                 + ' > //dev//xdevcfg')
        self.ask("nginx -p //opt//www//")
        self.ask('systemctl start redpitaya_nginx') # for 0.94 and higher #needs test
        sleep(self.delay)
        self.ask('ro')

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
                self.scp.put(os.path.join(self.dirname, 'monitor_server', serverfile), self.serverdirname+"monitor_server")
            except (SCPException, SSHException):
                self.logger.exception("Upload error. Try again after rebooting your RedPitaya..")
            sleep(self.delay)
            self.ask('chmod 755 ./monitor_server')
            sleep(self.delay)
            self.ask('ro')
            result = self.ask("./monitor_server " + str(self.port))
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
        result = self.ask(self.serverdirname+"/monitor_server " + str(self.port))
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
        self.ask('killall monitor_server') 
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

    def __del__(self):
        self.end()
        self.ssh.close()

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
        self.hk = rp.HK(self.client)
        self.ams = rp.AMS(self.client)
        self.scope = rp.Scope(self.client, self)
        self.pid0 = rp.Pid(self.client, module='pid0')
        self.pid1 = rp.Pid(self.client, module='pid1')
        self.pid2 = rp.Pid(self.client, module='pid2')
        self.pid3 = rp.Pid(self.client, module='pid3')
        self.iir = rp.IIR(self.client, module='iir')
        self.iq0 = rp.IQ(self.client, module='iq0')
        self.iq1 = rp.IQ(self.client, module='iq1')
        self.iq2 = rp.IQ(self.client, module='iq2')
        self.asg1 = rp.Asg1(self.client)
        self.asg2 = rp.Asg2(self.client)
        self.pwm0 = rp.AuxOutput(self.client,output='pwm0')
        self.pwm1 = rp.AuxOutput(self.client,output='pwm1')
        self.logger.info("Client started with success")

    def startdummyclient(self):
        self.client = monitor_client.DummyClient()
        self.hk = rp.HK(self.client)
        self.ams = rp.AMS(self.client)
        self.scope = rp.Scope(self.client, self)
        self.pid0 = rp.Pid(self.client, module='pid0')
        self.pid1 = rp.Pid(self.client, module='pid1')
        self.pid2 = rp.Pid(self.client, module='pid2')
        self.pid3 = rp.Pid(self.client, module='pid3')
        self.iir = rp.IIR(self.client, module='iir')
        self.iq0 = rp.IQ(self.client, module='iq0')
        self.iq1 = rp.IQ(self.client, module='iq1')
        self.iq2 = rp.IQ(self.client, module='iq2')
        self.asg1 = rp.Asg1(self.client)
        self.asg2 = rp.Asg2(self.client)
        self.pwm0 = rp.AuxOutput(self.client,output='pwm0')
        self.pwm1 = rp.AuxOutput(self.client,output='pwm1')
        self.logger.warning("Dummy mode started...")
    