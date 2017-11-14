from qtpy import QtWidgets, QtGui, QtCore
import socket
import logging

from ..sshshell import SshShell
from ..async_utils import APP


class HostnameSelectorWidget(QtWidgets.QDialog):
    _HIDE_PASSWORDS = False
    _SKIP_REDPITAYA_SIGNATURE = True  # display all devices incl. non-redpitayas
    _SCAN_TIMEOUT = 0.05
    _CONNECT_TIMEOUT = 1.0

    def __init__(self, parent=None, config={'user': None,
                                            'password': None,
                                            'sshport': None}):
        self.parent = parent
        self.items = []
        self.ips_and_macs = []
        self._logger = logging.getLogger(__name__)
        super(HostnameSelectorWidget, self).__init__()
        self.setWindowTitle('Red Pitaya connection - find a valid hostname')
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        self.hlay1 = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.hlay1)

        self.user_label = QtWidgets.QLabel('user')
        self.hlay1.addWidget(self.user_label)
        self.user_input = QtWidgets.QLineEdit(config['user'] or 'root')
        self.hlay1.addWidget(self.user_input)

        self.password_label = QtWidgets.QLabel('password')
        self.password_input = QtWidgets.QLineEdit(config['password'] or 'root')
        if self._HIDE_PASSWORDS:
            self.password_input.setEchoMode(self.password_input.PasswordEchoOnEdit)
        self.hlay1.addWidget(self.password_label)
        self.hlay1.addWidget(self.password_input)

        self.sshport_label = QtWidgets.QLabel('ssh port')
        self.sshport_input = QtWidgets.QLineEdit(text=str(config['sshport'] or 22))
        self.hlay1.addWidget(self.sshport_label)
        self.hlay1.addWidget(self.sshport_input)

        self.refresh = QtWidgets.QPushButton('Refresh list')
        self.refresh.clicked.connect(self.scan)
        self.hlay1.addWidget(self.refresh)

        self.progressbar = QtWidgets.QProgressBar(self)
        self.progressbar.setGeometry(200, 80, 250, 20)
        self.hlay1.addWidget(self.progressbar)
        self.progressbar.hide()

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(['IP address', 'MAC address'])
        self.layout.addWidget(self.tree)

        self.hlay2 = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.hlay2)

        self.hostname_label = QtWidgets.QLabel("Hostname")
        self.hostname_input = QtWidgets.QLineEdit()
        self.hostname_input.setPlaceholderText('e.g.: 192.168.1.100')
        self.hlay2.addWidget(self.hostname_label)
        self.hlay2.addWidget(self.hostname_input)

        self.hlay3 = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.hlay3)

        # cancel is not needed
        #self.cancel = QtWidgets.QPushButton("Cancel")
        #self.cancel.clicked.connect(self.hide)
        #self.hlay2.addWidget(self.cancel)

        self.ok_button = QtWidgets.QPushButton("OK")
        self.ok_button.clicked.connect(self.ok)
        self.ok_button.setDefault(True)
        self.hlay2.addWidget(self.ok_button)
        self.tree.itemSelectionChanged.connect(self.item_selected)
        self.tree.itemDoubleClicked.connect(self.item_double_clicked)
        self.scanning = False
        for signalname in ['cursorPositionChanged',
                           'editingFinished',
                           'returnPressed',
                           'selectionChanged',
                           'textChanged',
                           'textEdited']:
            for textbox in [self.user_input,
                            self.password_input,
                            self.sshport_input,
                            self.hostname_input]:
                getattr(textbox, signalname).connect(self.countdown_cancel)

    def showEvent(self, QShowEvent):
        ret = super(HostnameSelectorWidget, self).showEvent(QShowEvent)
        if not self.ips_and_macs:
            # launch autoscan at first startup with 10 ms delay
            self._aux_timer = QtCore.QTimer.singleShot(10, self.scan)
        return ret

    @property
    def hostname(self):
        return self.hostname_input.text()

    @hostname.setter
    def hostname(self, val):
        self.hostname_input.setText(val)

    @property
    def password(self):
        return self.password_input.text()

    @password.setter
    def password(self, val):
        self.password_input.setText(val)

    @property
    def user(self):
        return self.user_input.text()

    @user.setter
    def user(self, val):
        self.user_input.setText(val)

    @property
    def sshport(self):
        return int(self.sshport_input.text())

    @sshport.setter
    def sshport(self, val):
        self.sshport_input.setText(str(val))

    def item_selected(self):
        self.countdown_cancel()
        try:
            item = self.tree.selectedItems()[0]
        except: # pragma: no cover
            pass
        else:
            self.hostname = item.text(0)

    def item_double_clicked(self, item, row):
        self.countdown_cancel()
        self.hostname = item.text(0)
        self.ok()

    def ok(self):
        self.countdown_cancel()
        self.scanning = False
        self.hide()
        self.accept()

    @property
    def scanning(self):
        return self._scanning

    @scanning.setter
    def scanning(self, v):
        self._scanning = v
        # make refresh button inactive if scan is running
        self.refresh.setEnabled(not v)
        if v:
            self.refresh.setText("Searching LAN for Red Pitayas...")
        else:
            self.refresh.setText("Refresh list")
        self.sshport_input.setEnabled(not v)
        self.user_input.setEnabled(not v)
        self.password_input.setEnabled(not v)
        if v:
            self.progressbar.show()
        else:
            self.progressbar.hide()

    def _get_all_own_ip_addresses(self, exclude=['127.0.0.1']):
        """
        Returns a list of all ip addresses of the running computer

        Parameters:
            exclude (list of str): a list of ip addresses to exclude from the returned list

        Returns:
            list: list of internal ip addresses of all ipv4-able adapters of the computer
        """
        addr_list = []
        try:
            import netifaces
        except:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # doesn't even have to be reachable, just need an open socket
                s.connect(('10.255.255.255', 1))
                ip = s.getsockname()[0]
            except:  # pragma: no cover
                ip = '127.0.0.1'  # fall back to default if no network available
            finally:
                s.close()
            addr_list.append(ip)
        else:
            for interface in netifaces.interfaces():  # go through all interfaces (wlan, lan, etc.)
                try:
                    entries = netifaces.ifaddresses(interface)[netifaces.AF_INET]  # only use ipv4
                except KeyError:
                    pass
                else:
                    for entry in entries:  # iterate through all
                        try:
                            addr = entry['addr']  # collect ip address
                        except KeyError:
                            pass
                        else:
                            if addr not in exclude:  # exclude certain addresses (see above)
                                addr_list.append(addr)
        self._logger.debug("Your own ips are: %s", addr_list)
        return addr_list

    def scan(self):
        """
        Scan the local area network for available Red Pitayas.

        In order to work, the specified username and password must be correct.
        """
        self.countdown_cancel()
        if self.scanning: # pragma: no cover
            self._logger.debug("Scan is already running. Please wait for it "
                               "to finish before starting a new one! ")
            return
        else:
            self.progressbar.setValue(0)
            self.scanning = True
        # delete previous lists
        self.tree.clear()
        del self.items[:]  # self.items.clear() is not working in python < 3.3
        del self.ips_and_macs[:]
        # add fake device
        self.add_device("_FAKE_", "Simulated Red Pitaya")
        port = self.sshport
        user = self.user
        password = self.password
        # make a list of ips to scan for redpitayas
        ips = ['192.168.1.100']  # direct connection ip, not found automatically
        # first, find our own IP address to infer the LAN from it
        for ip in self._get_all_own_ip_addresses():
            # the LAN around an ip address 'a.b.c.d' is here defined here as all
            # ip addresses from a.b.c.0 to a.b.c.255
            end = ip.split('.')[-1]
            start = ip[:-len(end)]
            ips += [start + str(i) for i in range(256)]  # all local ips
        # start scanning all ips
        self.progressbar.setRange(0, len(ips))
        for i, ip in enumerate(ips):
            if not self.scanning:  # abort if ok was clicked prematurely
                return  # pragma: no cover
            # try SSH connection for all IP addresses
            self.progressbar.setValue(i)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self._SCAN_TIMEOUT)  # timeout is essentially network timescale
            err = s.connect_ex((ip, port))
            s.close()
            if err == 0:  # indicates that a SSH service is behind this IP
                self._logger.debug("%s:%d is open", ip, port)
                try:
                    # attempt to connect with username and password
                    ssh = SshShell(hostname=ip,
                                   user=user,
                                   password=password,
                                   timeout=self._CONNECT_TIMEOUT)  # longer timeout, RP is slow..
                except BaseException as e:
                    self._logger.debug('Cannot log in with user=%s, pw=%s '
                                       'at %s: %s', user, password, ip, e)
                else:
                    # login has worked, see if it is a Red Pitaya
                    macs = ssh.get_mac_addresses()
                    del ssh
                    for mac in macs:
                        # test for redpitaya signature in mac
                        if mac.startswith('00:26:32:') or self._SKIP_REDPITAYA_SIGNATURE:
                            self._logger.debug('RP device found: IP %s, '
                                               'MAC %s', ip, mac)
                            self.add_device(ip, mac)
            else:
                self._logger.debug("%s:%d is closed", ip, port)
            APP.processEvents()
        self.scanning = False
        if len(self.ips_and_macs) == 2:
            # exactly one device was found, therefore we can auto-proceed to
            # connection
            self.countdown_start() # pragma: no cover

    def countdown_start(self, countdown_s=10.0):
        self.countdown_cancel()
        self.countdown_cancelled = False
        self.countdown_remaining = countdown_s
        if not hasattr(self, 'countdown_timer'):
            self.countown_timer = QtCore.QTimer.singleShot(1, self.countdown_iteration)

    def countdown_iteration(self):
        if self.countdown_cancelled:
            return
        self.countdown_remaining -= 1
        self.ok_button.setText("OK (auto-clicked in %d s)"%self.countdown_remaining)
        if self.countdown_remaining >= 0:
            self.countown_timer = QtCore.QTimer.singleShot(1000, self.countdown_iteration)
        else:
            self.ok()

    def countdown_cancel(self, *args, **kwargs):
        self.countdown_cancelled = True
        self.ok_button.setText("OK")

    def add_device(self, hostname, token):
        self.ips_and_macs.append((hostname, token))
        item = QtWidgets.QTreeWidgetItem()
        item.setText(0, hostname)
        item.setText(1, token)
        self.items.append(item)
        self.tree.addTopLevelItem(item)
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)
        # if only one non-fake device is available
        if len(self.ips_and_macs) == 2 and self.hostname == '' or \
                self.hostname == hostname:
            self.hostname = hostname
            self.tree.clearSelection()
            item.setSelected(True)
        return item

    def remove_device(self, item):
        self.items.remove(item)
        self.tree.removeItemWidget(item, 0)

    def get_kwds(self):
        self.exec_()
        return dict(hostname=self.hostname,
                    password=self.password,
                    user=self.user,
                    sshport=self.sshport)
