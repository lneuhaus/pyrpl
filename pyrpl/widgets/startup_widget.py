from qtpy import QtWidgets, QtGui
import socket

from ..sshshell import SSHshell
from ..async_utils import APP


class HostnameSelectorWidget(QtWidgets.QDialog):
    def __init__(self):
        self.items = []
        super(HostnameSelectorWidget, self).__init__()
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        self.hlay1 = QtWidgets.QHBoxLayout()
        self.sshport_input = QtWidgets.QLineEdit(text="22")
        self.sshport_label = QtWidgets.QLabel('Ssh port')
        self.hlay1.addWidget(self.sshport_label)
        self.hlay1.addWidget(self.sshport_input)

        self.layout.addLayout(self.hlay1)
        self.user_label = QtWidgets.QLabel('user')
        self.hlay1.addWidget(self.user_label)
        self.user_input = QtWidgets.QLineEdit('root')
        self.hlay1.addWidget(self.user_input)

        self.password_label = QtWidgets.QLabel('password')
        self.password_input = QtWidgets.QLineEdit('root')
        self.password_input.setEchoMode(self.password_input.PasswordEchoOnEdit)
        self.hlay1.addWidget(self.password_label)
        self.hlay1.addWidget(self.password_input)
        self.refresh = QtWidgets.QPushButton('Refresh list')
        self.refresh.clicked.connect(self.browse)
        self.hlay1.addWidget(self.refresh)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(['IP addr.', 'MAC addr.'])
        self.layout.addWidget(self.tree)

        self.hlay2 = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.hlay2)

        self.hostname_label = QtWidgets.QLabel("Hostname")
        self.hostname_input = QtWidgets.QLineEdit()
        self.hlay2.addWidget(self.hostname_label)
        self.hlay2.addWidget(self.hostname_input)


        self.hlay3 = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.hlay3)

        self.cancel = QtWidgets.QPushButton("Cancel")
        self.cancel.clicked.connect(self.hide)
        self.hlay2.addWidget(self.cancel)

        self.ok_button = QtWidgets.QPushButton("OK")
        self.ok_button.clicked.connect(self.ok)
        self.hlay2.addWidget(self.ok_button)

        self.tree.itemDoubleClicked.connect(self.item_clicked)

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

    def item_clicked(self, item, row):
        self.hostname = item.text(0)

    def ok(self):
        STARTUP_WIDGET.hostname = self.hostname
        STARTUP_WIDGET.user = self.user
        STARTUP_WIDGET.sshport = self.sshport
        STARTUP_WIDGET.password = self.password
        self.hide()

    def browse(self):
        self.tree.clear()
        self.items.clear()
        port = self.sshport
        user = self.user
        password = self.password
        timeout = 0.01
        from time import sleep
        def get_ip():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # doesn't even have to be reachable
                s.connect(('10.255.255.255', 1))
                IP = s.getsockname()[0]
            except:
                IP = '127.0.0.1'
            finally:
                s.close()
            return IP

        ip = get_ip()
        # print("Your own ip is: %s" % ip)
        end = ip.split('.')[-1]
        start = ip[:-len(end)]
        ips = [start + str(i) for i in range(256)]
        sockets = []
        for ip in ips:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            # s.setblocking(1)
            err = s.connect_ex((ip, port))
            if err == 0:
                # print ("%s:%d is open"%(ip, port))
                s.close()
                try:
                    ssh = SSHshell(hostname=ip,
                                   user=user,
                                   password=password,
                                   timeout=1)
                except BaseException as e:
                    print('Cannot log in with user=root, pw=root at', ip, e)
                else:
                    # print "root pw works"
                    macs = list()
                    nextgood = False
                    for token in ssh.ask('ifconfig | grep HWaddr').split():
                        if nextgood and len(token.split(':')):
                            if token.startswith('00:26:32:'):
                                macs.append(token)
                                print('RP device: ', ip, token)
                                self.add_device(ip, token)
                        if token == 'HWaddr':
                            nextgood = True
                        else:
                            nextgood = False
                    # print(macs)
                    ssh.channel.close()
            else:
                s.close()
            APP.processEvents()

    def add_device(self, hostname, token):
        item = QtWidgets.QTreeWidgetItem()
        item.setText(0, hostname)
        item.setText(1, token)

        self.items.append(item)
        self.tree.addTopLevelItem(item)

class StartupWidget(QtWidgets.QDialog):
    host_selector = HostnameSelectorWidget()
    def __init__(self):
        super(StartupWidget, self).__init__()
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        self.hlay = QtWidgets.QHBoxLayout()

        self.layout.addLayout(self.hlay)

        self.hostname_input = QtWidgets.QLineEdit()
        self.hostname_input.setPlaceholderText('e.g.: 192.168.1.2')
        self.hostname_label = QtWidgets.QLabel("Hostname")
        self.sshport_label = QtWidgets.QLabel("Ssh port")
        self.sshport_input = QtWidgets.QLineEdit('22')

        self.hlay.addWidget(self.hostname_label)
        self.hlay.addWidget(self.hostname_input)

        self.browse_network = QtWidgets.QPushButton("Browse network...")
        self.browse_network.clicked.connect(self.browse)
        self.hlay.addWidget(self.browse_network)

        self.hlay2 = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.hlay2)

        self.user_label = QtWidgets.QLabel("User")
        self.user_input = QtWidgets.QLineEdit(text='root')
        self.hlay2.addWidget(self.user_label)
        self.hlay2.addWidget(self.user_input)

        self.password_input = QtWidgets.QLineEdit(text='root')
        self.password_label = QtWidgets.QLabel("Password")
        self.password_input.setEchoMode(QtWidgets.QLineEdit.PasswordEchoOnEdit)
        self.hlay2.addWidget(self.password_label)
        self.hlay2.addWidget(self.password_input)

        self.lay3 = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.lay3)
        self.connect_button = QtWidgets.QPushButton("Connect")
        self.lay3.addWidget(self.connect_button)
        self.connect_button.clicked.connect(self.accept)

    @property
    def sshport(self):
        return int(self.sshport_input.text())

    @sshport.setter
    def sshport(self, val):
        self.sshport_input.setText(str(val))

    @property
    def user(self):
        return self.user_input.text()

    @user.setter
    def user(self, val):
        self.user_input.setText(val)

    @property
    def password(self):
        return self.password_input.text()

    @password.setter
    def password(self, val):
        self.password_input.setText(val)

    @property
    def hostname(self):
        return self.hostname_input.text()

    @hostname.setter
    def hostname(self, val):
        self.hostname_input.setText(val)

    def browse(self):
        self.host_selector.sshport = self.sshport
        self.host_selector.user = self.user
        self.host_selector.password = self.password
        self.host_selector.exec_()

    def get_kwds(self):
        self.exec_()
        return dict(hostname=self.hostname,
                    password=self.password,
                    user=self.user,
                    sshport=self.sshport)

STARTUP_WIDGET = StartupWidget()
