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


import numpy as np
import time
from time import sleep
import socket


class MonitorClient(object):

    def __init__(self, address="192.168.1.0", port=2222, restartserver=None):
        """initiates a client connected to monitor_server

        address: server address, e.g. "localhost" or "192.168.1.0"
        port:    the port that the server is running on. 2222 by default
        restartserver: a function to call that restarts the server in case of problems
        """
        self._restartserver = restartserver
        self._address = address
        self._port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((self._address, self._port))
        except socket.error:
            "Socket error during connection." # mostly because of bad port
            self._port = self._restartserver() # try a different port here by putting port=-1
            self.socket.connect((address, self._port))
        self.socket.settimeout(1.0)  # 1 second timeout for socket operations

    def close(self):
        try:
            self.socket.send(
                'c' +
                chr(0) +
                chr(0) +
                chr(0) +
                chr(0) +
                chr(0) +
                chr(0) +
                chr(0))
            self.socket.close()
        except socket.error:
            return

    def __del__(self):
        self.close()
        
    #the public methods to use which will recover from connection problems
    def reads(self, addr, length):
        return self.trytwice(self._reads, addr, length)

    def writes(self, addr, values):
        return self.trytwice(self._writes, addr, values)
    
    #the actual code
    def _reads(self, addr, length):
        if length > 65535:
            length = 65535
            print "Maximum read-length is ", length
        header = 'r' + chr(0) + chr(length & 0xFF) + chr((length >> 8) & 0xFF) + chr(
            addr & 0xFF) + chr((addr >> 8) & 0xFF) + chr((addr >> 16) & 0xFF) + chr((addr >> 24) & 0xFF)
        self.socket.send(header)
        data = self.socket.recv(length * 4 + 8)
        while (len(data) < length * 4 + 8):
            data += self.socket.recv(length * 4 - len(data) + 8)
        if data[:8] == header:  # check for in-sync transmission
            return np.frombuffer(data[8:], dtype=np.uint32)
        else:  # error handling
            print "Error: wrong control sequence from server: ", data[:8]
            self.emptybuffer()
            return None

    def _writes(self, addr, values):
        values = values[:65535 - 2]
        length = len(values)
        header = 'w' + chr(0) + chr(length & 0xFF) + chr((length >> 8) & 0xFF) + chr(
            addr & 0xFF) + chr((addr >> 8) & 0xFF) + chr((addr >> 16) & 0xFF) + chr((addr >> 24) & 0xFF)
        # send header+body
        self.socket.send(header +
                         str(np.getbuffer(np.array(values, dtype=np.uint32))))
        if self.socket.recv(8) == header:  # check for in-sync transmission
            return True  # indicate successful write
        else:  # error handling
            print "Error: wrong control sequence from server"
            self.emptybuffer()
            return None

    def emptybuffer(self):
        for i in range(100):
            n = len(self.socket.recv(16384))
            if (n <= 0):
                return
            print "Read %d bytes from socket..." % n

    def trytwice(self, function, addr, value):
        try:
            value = function(addr, value)
        except (socket.timeout, socket.error):
            print "Timeout or socket error."
        else:
            if value is not None:
                return value
        print "Error occured. Trying a second time to read from redpitaya. "
        if self._restartserver is not None:
            self.restart()
        return function(addr, value)

    def restart(self):
        self.close()
        port = self._restartserver()
        self.__init__(
            address=self._address,
            port=port,
            restartserver=self._restartserver)

class DummyClient(object):
    
    def reads(self, addr, length):
        return np.zeros(length, dtype=np.uint32)

    def writes(self, addr, values):
        return True
    
    def restart(self):
        pass
    
    def close(self):
        pass