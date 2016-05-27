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


import paramiko
from time import sleep
from scp import SCPClient, SCPException
import os


class SSHshell(object):

    def __init__(
            self,
            hostname='localhost',
            user='root',
            password='root',
            verbose=True,
            delay=0.05):
        self.verbose = verbose
        self.delay = delay
        self.apprunning = False
        self.hostname = hostname
        self.user = user
        self.password = password
        self.port = 22
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(
            hostname,
            username=self.user,
            password=self.password,
            port=self.port,
            timeout=1)
        self.channel = self.ssh.invoke_shell()
        self.startscp()
        # self.sleep(0.1)
   
    def startscp(self):
        self.scp = SCPClient(self.ssh.get_transport())
        
    
    def write(self, text):
        if self.channel.send_ready() and not text == "":
            return self.channel.send(text)
        else:
            return -1

    def read_nbytes(self, nbytes):
        if self.channel.recv_ready():
            return self.channel.recv(nbytes)
        else:
            return ""

    def read(self):
        sumstring = ""
        string = "1"
        while string != "":
            string = self.read_nbytes(1024)
            sumstring += string
        self.log(sumstring)
        return sumstring

    def askraw(self, question=""):
        self.write(question)
        sleep(self.delay)
        return self.read()

    def ask(self, question=""):
        return self.askraw(question + '\n')

    def __del__(self):
        self.endapp()
        self.channel.close()
        self.ssh.close()

    def endapp(self):
        pass

    def reboot(self):
        self.endapp()
        self.ask("shutdown -r now")
        self.__del__()

    def shutdown(self):
        self.endapp()
        self.ask("shutdown now")
        self.__del__()

    def log(self, text):
        if self.verbose:
            print text
