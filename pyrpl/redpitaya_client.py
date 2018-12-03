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
import socket
import logging
try:
    raise  # disable sound output for now
    from pysine import sine  # for debugging read/write calls
except:
    def sine(frequency, duration):
        print("Called sine(frequency=%f, duration=%f)" % (frequency, duration))
from .hardware_modules.dsp import dsp_addr_base, DSP_INPUTS
from .pyrpl_utils import time

# global conter to assign a number to each client
# only used for debugging purposes
CLIENT_NUMBER = 0


class MonitorClient(object):
    def __init__(self, hostname="192.168.1.0", port=2222, restartserver=None):
        """initiates a client connected to monitor_server

        hostname: server address, e.g. "localhost" or "192.168.1.0"
        port:    the port that the server is running on. 2222 by default
        restartserver: a function to call that restarts the server in case of problems
        """
        self.logger = logging.getLogger(name=__name__)
        # update global client counter and assign a number to this client
        global CLIENT_NUMBER
        CLIENT_NUMBER += 1
        self.client_number = CLIENT_NUMBER
        self.logger.debug("Client number %s started", self.client_number)
        # start setting up client
        self._restartserver = restartserver
        self._hostname = hostname
        self._port = port
        self._read_counter = 0 # For debugging and unittests
        self._write_counter = 0 # For debugging and unittests
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # try to connect at least 5 times
        for i in range(5):
            if not self._port > 0:
                if self._port is None:
                    # likely means that _restartserver failed.
                    raise ValueError("Connection to hostname %s failed. "
                                     "Please check your connection parameters!"
                                     % (self._hostname))
                else:
                    raise ValueError("Trying to open MonitorClient for "
                                     "hostname %s on invalid port %s. Please "
                                     "check your connection parameters!"
                                     % (self._hostname, self._port))
            try:
                self.socket.connect((self._hostname, self._port))
            except socket.error:  # mostly because port is still closed
                self.logger.warning("Socket error during connection "
                                    "attempt %s.", i)
                # could try a different port here by putting port=-1
                self._port = self._restartserver()
            else:
                break
        self.socket.settimeout(1.0)  # 1 second timeout for socket operations

    def close(self):
        try:
            self.socket.send(
                b'c' + bytes(bytearray([0, 0, 0, 0, 0, 0, 0])))
            self.socket.close()
        except socket.error:
            return

    def __del__(self):
        self.close()
        
    # the public methods to use which will recover from connection problems
    def reads(self, addr, length):
        self._read_counter+=1
        if hasattr(self, '_sound_debug') and self._sound_debug:
            sine(440, 0.05)
        return self.try_n_times(self._reads, addr, length)

    def writes(self, addr, values):
        self._write_counter += 1
        if hasattr(self, '_sound_debug') and self._sound_debug:
            sine(880, 0.05)
        return self.try_n_times(self._writes, addr, values)
    
    # the actual code
    def _reads(self, addr, length):
        if length > 65535:
            length = 65535
            self.logger.warning("Maximum read-length is %d", length)
        header = b'r' + bytes(bytearray([0,
                                         length & 0xFF, (length >> 8) & 0xFF,
                                         addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF, (addr >> 24) & 0xFF]))
        self.socket.send(header)
        data = self.socket.recv(length * 4 + 8)
        while (len(data) < length * 4 + 8):
            data += self.socket.recv(length * 4 - len(data) + 8)
        if data[:8] == header:  # check for in-sync transmission
            return np.frombuffer(data[8:], dtype=np.uint32)
        else:  # error handling
            self.logger.error("Wrong control sequence from server: %s", data[:8])
            self.emptybuffer()
            return None

    def _writes(self, addr, values):
        values = values[:65535 - 2]
        length = len(values)
        header = b'w' + bytes(bytearray([0,
                                         length & 0xFF,
                                         (length >> 8) & 0xFF,
                                         addr & 0xFF,
                                         (addr >> 8) & 0xFF,
                                         (addr >> 16) & 0xFF,
                                         (addr >> 24) & 0xFF]))
        # send header+body
        self.socket.send(header +
                         np.array(values, dtype=np.uint32).tobytes())
        if self.socket.recv(8) == header:  # check for in-sync transmission
            return True  # indicate successful write
        else:  # error handling
            self.logger.error("Error: wrong control sequence from server")
            self.emptybuffer()
            return None

    def emptybuffer(self):
        for i in range(100):
            n = len(self.socket.recv(16384))
            if (n <= 0):
                return
            self.logger.debug("Read %d bytes from socket...", n)

    def try_n_times(self, function, addr, value, n=5):
        for i in range(n):
            try:
                value = function(addr, value)
            except (socket.timeout, socket.error):
                self.logger.error("Error occured in reading attempt %s. "
                                  "Reconnecting at addr %s to %s value %s by "
                                  "client %s"
                                  % (i,
                                     hex(addr),
                                     function.__name__,
                                     value,
                                     self.client_number))
                if self._restartserver is not None:
                    self.restart()
            else:
                if value is not None:
                    return value

    def restart(self):
        self.close()
        port = self._restartserver()
        self.__init__(
            hostname=self._hostname,
            port=port,
            restartserver=self._restartserver)


class DummyClient(object):  # pragma: no cover
    """Class for unitary tests without RedPitaya hardware available"""
    class fpgadict(dict):
        def __missing__(self, key):
            return 1 # 0 (1 is needed to avoid division_by_zero errors for some registers)
    fpgamemory = fpgadict({str(0x40100014): 1})  # scope decimation initial value

    def read_fpgamemory(self, addr):
        # here we implement a fraction of the memory map to simulate the actual redpitaya
        # scope
        offset = addr - 0x40100000
        # scope curve buffer
        if offset >= 0x10000 and offset < 0x30000:
            v = int(np.random.normal(scale=2**13 - 1))//4
            if v > 2**13-1:
                v = 2*13-1
            elif v < -(2**13-1):
                v = -(2**13-1)
            if v < 0:
                v += 2**14
            return v
        # scope control register - trigger armed, trigger source etc.
        if offset == 0:
            return 0
        if offset == 0x15C:  # current_timestamp lv part
            t = int(time()*125e6)
            return t % (2**32)
        if offset == 0x160:  # current_timestamp mv part
            return 0
            t = int(time()*125e6)
            return t - (t % (2**32))
        if offset == 0x164:  # trigger_timestamp lv part
            return 0
        if offset == 0x168:  # trigger_timestamp mv part
            return 0
        #DSP modules
        all = DSP_INPUTS
        for module in DSP_INPUTS:
            offset = addr - dsp_addr_base(module)
            if module.startswith('pid'):
                if offset == 0x220: # FILTERSTAGES
                    return 4
                elif offset == 0x228:  # MINBW
                    return 1
            elif module.startswith('iir'):
                if offset == 0x200:  # IIRBITS
                    return 64
                elif offset == 0x204:  # IIRSHIFT
                    return 32
                elif offset == 0x208:  # IIRSTAGES
                    return 16
                elif offset == 0x220:  # filterstages
                    return 1
                elif offset == 0x108:  # overflow
                    return 0
            elif module.startswith('iq'):
                if offset == 0x220:  # filterstages
                    return 1
                # rbw filter register
                elif offset == 0x230:  # filterstages = 0x230
                    return 2
                elif offset == 0x234:  # shiftbits = 0x234
                    return 2
                elif offset == 0x238:  # minbw = 0x238
                    return 1
            for filter_module in ['iq', 'pid', 'iir']:
                if module.startswith(filter_module):
                    if offset == 0x220:  # filterstages
                        return 1
                    elif offset == 0x224:  # shiftbits
                        return 2
                    elif offset == 0x228:  # minbw
                        return 1

        # everything else is restored from the dict
        return self.fpgamemory[str(addr)]

    def reads(self, addr, length):
        val = []
        for i in range(length):
            val.append(self.read_fpgamemory(addr+0x4*i))
        return np.array(val, dtype=np.uint32)
    
    def writes(self, addr, values): # pragma: no-cover
        for i, v in enumerate(values):
            self.fpgamemory[str(addr+0x4*i)]=v
    
    def restart(self):
        pass
    
    def close(self):
        pass