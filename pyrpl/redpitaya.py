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

import contextlib
import hashlib
import logging
import os
import random
import re
import tempfile
from collections import OrderedDict
from time import sleep

from paramiko import SSHException
from scp import SCPException

from . import hardware_modules as rp
from . import redpitaya_client
from .errors import ExpectedPyrplError
from .fpga_profiles import get_fpga_profile
from .hardware_modules.dsp import DSP_INPUTS
from .memory import MemoryTree
from .pyrpl_utils import (
    get_unique_name_list_from_class_list,
    update_with_typeconversion,
)
from .sshshell import SshShell
from .widgets.startup_widget import HostnameSelectorWidget

# default parameters for redpitaya object creation
defaultparameters = dict(
    hostname="",  #'192.168.1.100', # the ip or hostname of the board, '' triggers gui
    port=2222,  # port for PyRPL datacommunication
    sshport=22,  # port of ssh server - default 22
    user="root",
    password="root",
    delay=0.05,  # delay between ssh commands - console is too slow otherwise
    autostart=True,  # autostart the client?
    reloadserver=False,  # reinstall the server at startup if not necessary?
    reloadfpga="auto",  # reload the fpga binfile at startup? True/False/'auto'
    fpga_profile="default",  # packaged FPGA hardware/software profile
    filename="fpga/red_pitaya.bin",  # old path is migrated to the selected profile
    dtbo_filename="fpga/red_pitaya.dtbo",  # old path is migrated to the selected profile
    # name of the binfile on the server and in the device tree overlay file
    serverbinfilename="fpga.bin",
    serverdtbofilename="fpga.dtbo",  # name of the device tree overlay file on the server
    serverdirname="//opt//pyrpl//",  # server directory for server app and bitfile
    leds_off=True,  # turn off all GPIO lets at startup (improves analog performance)
    frequency_correction=1.0,  # actual FPGA frequency is 125 MHz * frequency_correction
    timeout=1,  # timeout in seconds for ssh communication
    monitor_server_name="monitor_server",  # name of the server program on redpitaya
    scpi_server=False,  # start the read-only SCPI server for other acquisition programs?
    scpi_port=5000,  # port of the read-only SCPI server
    scpi_server_name="pyrpl_scpi_server",  # name of the SCPI server program on redpitaya
    silence_env=False,  # suppress all environment variables that may override the configuration?
    gui=True,  # show graphical user interface or work on command-line only?
)


class RedPitaya:
    def __init__(
        self,
        config=None,  # configfile is needed to store parameters. None simulates one
        **kwargs,
    ):
        """this class provides the basic interface to the redpitaya board

        The constructor installs and starts the communication interface on the RedPitaya
        at 'hostname' that allows remote control and readout

        'config' is the config file or MemoryTree of the config file. All keyword arguments
        may be specified in the branch 'redpitaya' of this config file. Alternatively,
        they can be overwritten by keyword arguments at the function call.

        'config=None' specifies that no persistent config file is saved on the disc.

        Possible keyword arguments and their defaults are:
            hostname='192.168.1.100', # the ip or hostname of the board
            port=2222,  # port for PyRPL datacommunication
            sshport=22,  # port of ssh server - default 22
            user='root',
            password='root',
            delay=0.05,  # delay between ssh commands - console is too slow otherwise
            autostart=True,  # autostart the client?
            reloadserver=False,  # reinstall the server at startup if not necessary?
            reloadfpga='auto',  # reload the fpga bitfile at startup? True/False/'auto'
            fpga_profile='default',  # packaged FPGA hardware/software profile
            filename='fpga/red_pitaya.bin',  # migrated to the selected profile
            dtbo_filename='fpga/red_pitaya.dtbo', # migrated to the selected profile
            # name of the binfile on the server and in the device tree overlay file
            serverbinfilename='fpga.bin',
            serverdtbofilename='fpga.dtbo',  # name of the device tree overlay file on the server
            serverdirname = "//opt//pyrpl//",  # server directory for server app and bitfile
            leds_off=True,  # turn off all GPIO lets at startup (improves analog performance)
            frequency_correction=1.0,  # actual FPGA frequency is 125 MHz * frequency_correction
            timeout=3,  # timeout in seconds for ssh communication
            monitor_server_name='monitor_server',  # name of the server program on redpitaya
            scpi_server=False,  # start the read-only SCPI server for other programs?
            scpi_port=5000,  # port of the read-only SCPI server
            scpi_server_name='pyrpl_scpi_server',  # name of the SCPI server program
            # suppress all environment variables that may override the configuration?
            silence_env=False,
            gui=True  # show graphical user interface or work on command-line only?

        if you are experiencing problems, try to increase delay, or try
        logging.getLogger().setLevel(logging.DEBUG)"""
        self.logger = logging.getLogger(name=__name__)
        # self.license()
        # make or retrieve the config file
        if isinstance(config, MemoryTree):
            self.c = config
        else:
            self.c = MemoryTree(config)
        # get the parameters right (in order of increasing priority):
        # 1. defaults
        # 2. environment variables
        # 3. config file
        # 4. command line arguments
        # 5. (if missing information) request from GUI or command-line
        self.parameters = dict(defaultparameters)

        # get parameters from os.environment variables
        if not self.parameters["silence_env"]:
            for k in self.parameters:
                if "REDPITAYA_" + k.upper() in os.environ:
                    newvalue = os.environ["REDPITAYA_" + k.upper()]
                    oldvalue = self.parameters[k]
                    self.parameters[k] = type(oldvalue)(newvalue)
                    if k == "password":  # do not show the password on the screen
                        oldvalue = "********"
                        newvalue = "********"
                    self.logger.debug(
                        "Variable %s with value %s overwritten "
                        "by environment variable REDPITAYA_%s "
                        "with value %s. Use argument "
                        "'silence_env=True' if this is not "
                        "desired!",
                        k,
                        oldvalue,
                        k.upper(),
                        newvalue,
                    )
        # settings from config file
        try:
            update_with_typeconversion(self.parameters, self.c._get_or_create("redpitaya")._data)
        except Exception as e:
            self.logger.warning(
                "An error occured during the loading of your "
                "Red Pitaya settings from the config file: %s",
                e,
            )
        # settings from class initialisation / command line
        update_with_typeconversion(self.parameters, kwargs)

        # Resolve the profile before connecting, flashing, or constructing
        # modules. Existing configurations commonly contain the old package
        # paths; treat those and other managed profile paths as defaults unless
        # the caller explicitly supplied a custom filename.
        self.fpga_profile = get_fpga_profile(self.parameters["fpga_profile"])
        self.parameters["fpga_profile"] = self.fpga_profile.id
        self.cls_modules = tuple(
            getattr(rp, class_name) for class_name in self.fpga_profile.hardware_modules
        )
        self._resolve_profile_files(
            filename_explicit="filename" in kwargs,
            dtbo_filename_explicit="dtbo_filename" in kwargs,
        )
        # get missing connection settings from gui/command line
        if self.parameters["hostname"] is None or self.parameters["hostname"] == "":
            gui = "gui" not in self.c._keys() or self.c.gui
            if gui:
                self.logger.info(
                    "Please choose the hostname of your Red Pitaya in the hostname selector window!"
                )
                startup_widget = HostnameSelectorWidget(config=self.parameters)
                hostname_kwds = startup_widget.get_kwds()
            else:
                hostname = input("Enter hostname [192.168.1.100]: ")
                hostname = "192.168.1.100" if hostname == "" else hostname
                hostname_kwds = dict(hostname=hostname)
                if "sshport" not in kwargs:
                    sshport = input("Enter sshport [22]: ")
                    sshport = 22 if sshport == "" else int(sshport)
                    hostname_kwds["sshport"] = sshport
                if "user" not in kwargs:
                    user = input("Enter username [root]: ")
                    user = "root" if user == "" else user
                    hostname_kwds["user"] = user
                if "password" not in kwargs:
                    password = input("Enter password [root]: ")
                    password = "root" if password == "" else password
                    hostname_kwds["password"] = password
            self.parameters.update(hostname_kwds)

        # optional: write configuration back to config file
        self.c["redpitaya"] = self.parameters

        # save default port definition for possible automatic port change
        self.parameters["defaultport"] = self.parameters["port"]
        # frequency_correction is accessed by child modules
        self.frequency_correction = self.parameters["frequency_correction"]
        # memorize whether server is running - nearly obsolete
        self._serverrunning = False
        self.client = None  # client class
        self._slaves = []  # slave interfaces to same redpitaya
        self.modules = OrderedDict()  # all submodules

        # provide option to simulate a RedPitaya
        if self.parameters["hostname"] in ["_FAKE_REDPITAYA_", "_FAKE_"]:
            self.startdummyclient()
            self.logger.warning(
                "Simulating RedPitaya because (hostname=="
                + self.parameters["hostname"]
                + "). Incomplete "
                "functionality possible. "
            )
            return
        elif self.parameters["hostname"] in ["_NONE_"]:
            self.modules = []
            self.logger.warning(
                "No RedPitaya created (hostname==" + self.parameters["hostname"] + ")."
                " No hardware modules are available. "
            )
            return
        # connect to the redpitaya board
        self.start_ssh()
        # start other stuff
        self.get_os_version()  # get os version for later use
        self._configure_os_compatibility()

        # Handle reloadfpga with auto option
        should_reload_fpga = self._should_reload_fpga()

        if should_reload_fpga:  # flash fpga
            self._update_fpga()
        if self._should_reload_server():  # install/reinstall server app
            self.installserver()
        if self.parameters["autostart"]:  # start client
            self.start()
        self.logger.info(f"Successfully connected to Redpitaya with hostname {self.ssh.hostname}.")
        self.parent = self

    def _resolve_profile_files(self, filename_explicit=False, dtbo_filename_explicit=False):
        """Select packaged profile files while preserving explicit overrides."""

        def is_managed_path(value, basename):
            if value in (None, ""):
                return True
            normalized = str(value).replace("\\", "/")
            return normalized == f"fpga/{basename}" or normalized.startswith("fpga/bitstreams/")

        if not filename_explicit and is_managed_path(
            self.parameters.get("filename"), "red_pitaya.bin"
        ):
            self.parameters["filename"] = os.path.relpath(
                self.fpga_profile.bitstream, os.path.dirname(__file__)
            )
        if not dtbo_filename_explicit and is_managed_path(
            self.parameters.get("dtbo_filename"), "red_pitaya.dtbo"
        ):
            self.parameters["dtbo_filename"] = os.path.relpath(
                self.fpga_profile.dtbo, os.path.dirname(__file__)
            )

    def _configure_os_compatibility(self):
        """Apply settings imposed by the detected Red Pitaya OS."""
        if self.os_version.startswith("3."):
            # OS 3 overlay.sh currently copies these fixed names from
            # /opt/pyrpl, regardless of the paths passed on its command line.
            required_binfilename = "fpga.bin"
        elif self.os_version.startswith("2."):
            # OS 2 overlay.sh ignores the image path passed on its command
            # line and requests this fixed firmware name from /opt/pyrpl.
            required_binfilename = "fpga.bit.bin"
        else:
            return

        if self.parameters["serverbinfilename"] != required_binfilename:
            self.logger.info(
                "Red Pitaya OS %s requires serverbinfilename=%s; overriding saved value %s",
                self.os_version,
                required_binfilename,
                self.parameters["serverbinfilename"],
            )
            self.parameters["serverbinfilename"] = required_binfilename
            self.c["redpitaya"] = self.parameters

    def _should_reload_server(self):
        """Return whether the bundled monitor server must be installed."""
        if self.parameters["reloadserver"]:
            return True
        if not self.os_version.startswith("3."):
            return False

        server_path = self.parameters["serverdirname"] + self.parameters["monitor_server_name"]
        self.ssh.ask()
        result = self.ssh.ask(f"readelf -l {server_path} 2>&1")
        if "/lib/ld-linux-armhf.so.3" in result:
            self.logger.debug("Compatible OS 3 monitor_server already installed")
            return False

        self.logger.info(
            "Installing the OS 3 compatible hard-float monitor_server at %s",
            server_path,
        )
        return True

    def _should_reload_fpga(self):
        """
        Determine if FPGA should be reloaded based on reloadfpga parameter.

        Returns:
            bool: True if FPGA should be reloaded, False otherwise
        """
        reloadfpga = self.parameters["reloadfpga"]

        # Handle True/False cases
        if reloadfpga is True or reloadfpga == "true" or reloadfpga == "True":
            self.logger.debug("reloadfpga=True: FPGA will be reloaded")
            return True
        elif reloadfpga is False or reloadfpga == "false" or reloadfpga == "False":
            self.logger.debug("reloadfpga=False: FPGA will not be reloaded")

        # Handle 'auto' case
        elif reloadfpga == "auto":
            self.logger.debug("reloadfpga='auto': checking if proper image is loaded")
            if self._is_correct_fpga_image_loaded():
                self.logger.info("Correct FPGA image detected, skipping reload")
                return False
            else:
                self.logger.info("Correct FPGA image not detected, will reload")
                return True
        else:
            self.logger.warning("Unknown reloadfpga value '%s', defaulting to auto", reloadfpga)
            return self._should_reload_fpga() if self.parameters["reloadfpga"] == "auto" else True

    def _is_correct_fpga_image_loaded(self):
        """
        Check if the correct FPGA image is currently loaded.

        Returns:
            bool: True if correct image is loaded, False otherwise
        """
        try:
            # Check /tmp/loaded_fpga.inf to see what's currently loaded
            self.ssh.ask()  # clear buffer
            result = self.ssh.ask("cat /tmp/loaded_fpga.inf")
            self.logger.debug("Current FPGA image: %s", result)

            expected_image = "pyrpl" in result.lower()
            if self.os_version.startswith("3."):
                # OS 3 can leave a pyrpl marker behind even when overlay.sh
                # failed. Also require the fixed filename used by that script.
                expected_image = expected_image and "fpga.bin" in result.lower()

            # Until the RTL exposes a fixed profile-ID register, use a
            # per-boot marker written only after a successful profile load.
            self.ssh.ask()
            loaded_profile = self.ssh.ask("cat /tmp/pyrpl_fpga_profile 2>/dev/null")
            expected_image = expected_image and self.fpga_profile.id in loaded_profile.split()

            if expected_image:
                self.logger.debug("FPGA already loaded with PyRPL image")
                return True
            else:
                self.logger.debug("FPGA loaded with different image: %s", result)
                return False

        except (AttributeError, OSError, RuntimeError) as e:
            self.logger.warning("Could not determine FPGA image status: %s", e)
            # If we can't check, assume we need to reload
            return False

    def start_ssh(self, attempt=0):
        """
        Establishes an ssh connection to the RedPitaya board

        returns True if a successful connection has been established
        """
        with contextlib.suppress(AttributeError, OSError, RuntimeError):
            # close pre-existing connection if necessary
            self.end_ssh()
        if self.parameters["hostname"] == "_FAKE_REDPITAYA_":
            # simulation mode - start without connecting
            self.logger.warning("(Re-)starting client in dummy mode...")
            self.startdummyclient()
            return True
        else:  # normal mode - establish ssh connection and
            try:
                # start ssh connection
                self.ssh = SshShell(
                    hostname=self.parameters["hostname"],
                    sshport=self.parameters["sshport"],
                    user=self.parameters["user"],
                    password=self.parameters["password"],
                    delay=self.parameters["delay"],
                    timeout=self.parameters["timeout"],
                )
                # test ssh connection for exceptions
                self.ssh.ask()
            except Exception as e:  # connection problem
                if attempt < 3:
                    # try to connect up to 3 times
                    return self.start_ssh(attempt=attempt + 1)
                else:  # even multiple attempts did not work
                    raise ExpectedPyrplError(
                        "\nCould not connect to the Red Pitaya device with "
                        "the following parameters: \n\n"
                        "\thostname: {}\n"
                        "\tssh port: {}\n"
                        "\tusername: {}\n"
                        "\tpassword: ****\n\n"
                        "Please confirm that the device is reachable by typing "
                        "its hostname/ip address into a web browser and "
                        "checking that a page is displayed. \n\n"
                        "Error message: {}".format(
                            self.parameters["hostname"],
                            self.parameters["sshport"],
                            self.parameters["user"],
                            e,
                        )
                    ) from e
            else:
                # everything went well, connection is established
                # also establish scp connection
                self.ssh.startscp()
                return True

    def switch_led(self, gpiopin=0, state=False):
        self.ssh.ask("echo " + str(gpiopin) + " > /sys/class/gpio/export")
        sleep(self.parameters["delay"])
        self.ssh.ask("echo out > /sys/class/gpio/gpio" + str(gpiopin) + "/direction")
        sleep(self.parameters["delay"])
        state = "1" if state else "0"
        self.ssh.ask("echo " + state + " > /sys/class/gpio/gpio" + str(gpiopin) + "/value")
        sleep(self.parameters["delay"])

    def put_file(self, source, destination):
        last_error = None
        for _i in range(3):
            try:
                self.ssh.scp.put(source, destination)
            except (SCPException, SSHException) as error:
                last_error = error
                # try again before failing
                self.start_ssh()
                sleep(self.parameters["delay"])
            else:
                return
        raise OSError(f"Could not upload {source!r} to {destination!r}") from last_error

    def get_os_version(self):
        self.ssh.ask()  # clear buffer
        result = self.ssh.ask("cat /root/.version")
        self.logger.debug(f"cat /root/.version: {result}")

        # Interactive SSH output can contain CRLF, LF, prompts and invisible
        # terminal control bytes on the same line. The command and prompt do
        # not contain a dotted numeric token, so extract that token directly.
        match = re.search(r"(?<![\d.])(\d+(?:\.\d+)+)(?![\d.])", result)
        if match is None:
            self.logger.warning(f"Could not parse OS version from response: {result}")
            version = "unknown"
        else:
            version = match.group(1)
        self.logger.debug("OS version: %s", version)
        self.os_version = version

    def update_fpga(self, filename=None, dtbo_filename=None):
        should_reload = self._should_reload_fpga()
        if not should_reload:
            self.logger.error(
                "FPGA update not completed - reloadfpga is False or auto-detected as not needed"
            )
            return

        self._update_fpga(filename, dtbo_filename)

    def _update_fpga(self, filename=None, dtbo_filename=None):
        source = None
        # Determine the base directory for finding files
        base_dir = os.path.abspath(os.path.dirname(__file__))
        self.logger.debug("Base directory: %s", base_dir)

        # Get the source file, with priority order:
        # 1. Function parameter
        # 2. Config parameter
        # 3. Default file (fpga/red_pitaya.bin in the package)
        if filename is not None:
            source = filename
        elif "filename" in self.parameters and self.parameters["filename"]:
            source = self.parameters["filename"]
        else:
            # Use default from package
            source = "fpga/red_pitaya.bin"

        # If source is relative, make it absolute relative to base_dir
        if not os.path.isabs(source):
            source = os.path.join(base_dir, source)

        # Check if file exists
        self.logger.debug("Checking for FPGA binfile at: %s", source)
        if not os.path.isfile(source):
            # List what files are available in the expected directory for debugging
            expected_dir = os.path.dirname(source)
            if os.path.isdir(expected_dir):
                self.logger.error("FPGA binfile not found at: %s", source)
                self.logger.error("Files in %s: %s", expected_dir, os.listdir(expected_dir))
            else:
                self.logger.error("FPGA binfile not found at: %s", source)
                self.logger.error("Directory does not exist: %s", expected_dir)

            raise OSError(
                "FPGA binfile not found",
                "The fpga binfile was not found at: " + source + "\n"
                "Please ensure the file exists or specify a different file with the filename "
                "parameter.",
            )

        self.logger.info("Found FPGA binfile at: %s", source)

        # Get the dtbo source file with same priority order
        dtbo_source = None
        if dtbo_filename is not None:
            dtbo_source = dtbo_filename
        elif "dtbo_filename" in self.parameters and self.parameters["dtbo_filename"]:
            dtbo_source = self.parameters["dtbo_filename"]
        else:
            # Use default dtbo from package (optional)
            dtbo_source = "fpga/red_pitaya.dtbo"

        # If dtbo_source is relative, make it absolute relative to base_dir
        if dtbo_source is not None and not os.path.isabs(dtbo_source):
            dtbo_source = os.path.join(base_dir, dtbo_source)

        # Check if dtbo file exists (it's optional, so just warn if missing)
        if dtbo_source is not None:
            if os.path.isfile(dtbo_source):
                self.logger.info("Found DTBO file at: %s", dtbo_source)
            else:
                self.logger.warning(
                    "DTBO file not found at: %s (continuing without it)", dtbo_source
                )
                dtbo_source = None

        # Prepare the system
        self.end()
        sleep(self.parameters["delay"])
        self.ssh.ask("rw")
        sleep(self.parameters["delay"])
        self.ssh.ask("mkdir -p " + self.parameters["serverdirname"])
        sleep(self.parameters["delay"])

        # send binfile after all checks
        bin_file_path = os.path.join(
            self.parameters["serverdirname"], self.parameters["serverbinfilename"]
        )
        self.put_file(source, bin_file_path)

        update_cmd = f"/opt/redpitaya/sbin/overlay.sh pyrpl {bin_file_path}"

        # add dtbo file to command if it exists
        if dtbo_source is not None:
            dtbo_file_path = os.path.join(
                self.parameters["serverdirname"], self.parameters["serverdtbofilename"]
            )
            dtbo_to_upload = dtbo_source
            temporary_dtbo = None
            if self.os_version.startswith("3."):
                # fpgautil on OS 3 stages the image as fpga.bin. Keep the
                # original DTBO for older systems, but update its fixed-width
                # firmware-name string in the temporary upload copy.
                old_name = b"fpga.bit.bin\x00"
                new_name = b"fpga.bin\x00" + b"\x00" * (len(old_name) - len(b"fpga.bin\x00"))
                with open(dtbo_source, "rb") as source_file:
                    dtbo_data = source_file.read()
                if old_name not in dtbo_data:
                    raise OSError(
                        "OS 3 DTBO conversion failed: firmware-name "
                        f"fpga.bit.bin was not found in {dtbo_source}"
                    )
                with tempfile.NamedTemporaryFile(suffix=".dtbo", delete=False) as temporary_dtbo:
                    temporary_dtbo.write(dtbo_data.replace(old_name, new_name, 1))
                    temporary_dtbo.close()
                    dtbo_to_upload = temporary_dtbo.name
            try:
                self.put_file(dtbo_to_upload, dtbo_file_path)
            finally:
                if temporary_dtbo is not None:
                    os.unlink(temporary_dtbo.name)
            update_cmd = f"{update_cmd} {dtbo_file_path}"

        # kill all other servers to prevent reading while fpga is flashed
        self.end()
        # also an SCPI server left running by a previous session
        self.endscpiserver()
        self.ssh.ask("killall nginx")
        self.ssh.ask("systemctl stop redpitaya_nginx")  # for 0.94 and higher
        sleep(3)  # sleep after stopping service

        overlay_error = None
        if self.os_version.find("2.") != -1 or self.os_version.find("3.") != -1:  # for os >= 0.94
            result = self.ssh.ask(update_cmd)
            sleep(1)
            result += self.ssh.ask()
            result += self.ssh.ask("cat /tmp/update_fpga.txt")
            if "failed" in result.lower() or "cannot stat" in result.lower():
                diagnostics = self.ssh.ask("cat /sys/class/fpga_manager/fpga0/state 2>&1")
                diagnostics += self.ssh.ask("dmesg | tail -50")
                overlay_error = result + "\nFPGA manager and kernel diagnostics:\n" + diagnostics
        else:
            # Old OS version - use xdevcfg directly
            self.logger.info("Loading FPGA via xdevcfg (old OS version)")
            self.ssh.ask(
                "cat "
                + os.path.join(
                    self.parameters["serverdirname"],
                    self.parameters["serverbinfilename"],
                )
                + " > //dev//xdevcfg"
            )

        sleep(3.0)  # wait a bit for the fpga to be programmed
        self.logger.debug("About to restart the redpitaya service")

        # Keep failed inputs on the board for manual fpgautil/dmesg
        # diagnostics. Successful loads no longer need the temporary files.
        if overlay_error is None:
            self.ssh.ask(f"printf '{self.fpga_profile.id}\\n' > /tmp/pyrpl_fpga_profile")
            self.ssh.ask(
                "rm -f "
                + os.path.join(
                    self.parameters["serverdirname"], self.parameters["serverdtbofilename"]
                )
            )
            self.ssh.ask(
                "rm -f "
                + os.path.join(
                    self.parameters["serverdirname"], self.parameters["serverbinfilename"]
                )
            )

        self.ssh.ask("nginx -p //opt//www//")
        self.ssh.ask("systemctl start redpitaya_nginx")  # for 0.94 and higher
        sleep(self.parameters["delay"])
        self.ssh.ask("ro")

        if overlay_error is not None:
            raise OSError(f"FPGA overlay loading failed:\n{overlay_error}")

    def serverbinfileexists(self):
        self.ssh.ask()
        result = self.ssh.ask(
            "ls {}".format(
                os.path.join(
                    self.parameters["serverdirname"],
                    self.parameters["serverbinfilename"],
                )
            )
        )
        self.logger.debug(f"ls serverbinfilename result: {result}")

        return result.find("No such file or directory") < 0

    def fpgarecentlyflashed(self):
        if not self.serverbinfileexists():
            return False

        self.ssh.ask()
        result = self.ssh.ask(
            'echo $(($(date +%s) - $(date +%s -r "'
            + os.path.join(self.parameters["serverdirname"], self.parameters["serverbinfilename"])
            + '")))'
        )
        age = None
        for line in result.split("\r"):
            try:
                age = int(line.strip())
            except (TypeError, ValueError):
                pass
            else:
                break
        if not age:
            self.logger.debug("Could not retrieve bitfile age from: {}".format(result.split("\r")))
            return False
        elif age > 10:
            self.logger.debug("Found expired bitfile. Age: %s", age)
            return False
        else:
            self.logger.debug("Found recent bitfile. Age: %s", age)
            return True

    def installserver(self):
        self.endserver()
        sleep(self.parameters["delay"])
        self.ssh.ask("rw")
        sleep(self.parameters["delay"])
        self.ssh.ask("mkdir -p " + self.parameters["serverdirname"])
        sleep(self.parameters["delay"])
        self.ssh.ask("cd " + self.parameters["serverdirname"])
        # try both versions

        if self.os_version.startswith("3."):
            serverfiles = ["monitor_server_0.95"]
        else:
            serverfiles = ["monitor_server", "monitor_server_0.95"]

        for serverfile in serverfiles:
            sleep(self.parameters["delay"])
            self.put_file(
                os.path.join(
                    os.path.abspath(os.path.dirname(__file__)),
                    "monitor_server",
                    serverfile,
                ),
                self.parameters["serverdirname"] + self.parameters["monitor_server_name"],
            )
            sleep(self.parameters["delay"])
            self.ssh.ask("chmod 755 ./" + self.parameters["monitor_server_name"])
            sleep(self.parameters["delay"])
            self.ssh.ask("ro")
            result = self.ssh.ask(
                "./" + self.parameters["monitor_server_name"] + " " + str(self.parameters["port"])
            )
            sleep(self.parameters["delay"])
            result += self.ssh.ask()
            if "sh" not in result:
                self.logger.debug("Server application started on port %d", self.parameters["port"])
                return self.parameters["port"]
            else:  # means we tried the wrong binary version. make sure server is not running and
                # try again with next file
                self.endserver()

        # try once more on a different port
        if self.parameters["port"] == self.parameters["defaultport"]:
            self.parameters["port"] = random.randint(self.parameters["defaultport"], 50000)
            self.logger.warning(
                "Problems to start the server application. "
                "Trying again with a different port number %d",
                self.parameters["port"],
            )
            return self.installserver()

        self.logger.error(
            "Server application could not be started. Try to recompile monitor_server on your "
            "RedPitaya (see manual). "
        )
        return None

    def startserver(self):
        self.endserver()
        sleep(self.parameters["delay"])
        if self.fpgarecentlyflashed():
            self.logger.info("FPGA is being flashed. Please wait for 2 seconds.")
            sleep(3.0)  # extra second wait time after flashing to avoid bug with the exe
        result = self.ssh.ask(
            self.parameters["serverdirname"]
            + "/"
            + self.parameters["monitor_server_name"]
            + " "
            + str(self.parameters["port"])
        )
        if "sh" not in result:  # sh in result means we tried the wrong binary version
            self.logger.debug("Server application started on port %d", self.parameters["port"])
            self._serverrunning = True
            return self.parameters["port"]
        # something went wrong
        return self.installserver()

    def endserver(self):
        # Simulated RedPitaya instances have a dummy client but no SSH shell
        # or remote monitor_server to stop.
        if not hasattr(self, "ssh"):
            self._serverrunning = False
            return
        try:
            self.ssh.ask("\x03")  # exit running server application
        except (AttributeError, OSError, RuntimeError):
            self.logger.exception("Server not responding...")
        if "pitaya" in self.ssh.ask():
            self.logger.debug(">")  # formerly 'console ready'
        sleep(self.parameters["delay"])
        # make sure no other monitor_server blocks the port
        self.ssh.ask("killall " + self.parameters["monitor_server_name"])
        self._serverrunning = False

    def _scpi_server_path(self):
        return self.parameters["serverdirname"] + self.parameters["scpi_server_name"]

    def _scpi_server_command(self):
        """Command line of the SCPI server for the loaded FPGA profile."""
        available = self.fpga_profile.hardware.get("dsp_inputs", list(DSP_INPUTS))
        signals = ",".join(
            f"{name}={index}" for name, index in DSP_INPUTS.items() if name in available
        )
        return (
            f"{self._scpi_server_path()} -p {int(self.parameters['scpi_port'])} "
            f"-i {self.fpga_profile.id} -s {signals}"
        )

    def _ssh_exec(self, command, timeout=10):
        """Runs a command on its own ssh channel and returns stdout + stderr.

        Unlike self.ssh.ask, this works while monitor_server occupies the
        interactive shell, so the SCPI server can be managed at any time
        without stopping the connection of PyRPL."""
        _, stdout, stderr = self.ssh.ssh.exec_command(command, timeout=timeout)
        return stdout.read().decode(errors="replace") + stderr.read().decode(errors="replace")

    def _scpi_server_cmdline(self):
        """Command line of the running SCPI server, or '' if it is not running."""
        # arguments are separated by NUL bytes; converted here rather than with
        # tr, as a NUL byte in an ssh command makes sshd drop the connection
        result = self._ssh_exec(
            "cat /proc/$(pidof -s {})/cmdline 2>/dev/null".format(
                self.parameters["scpi_server_name"]
            )
        ).replace("\x00", " ")
        return result if self.parameters["scpi_server_name"] + " -p" in result else ""

    def installscpiserver(self):
        """Uploads the SCPI server binary unless the board has the same one."""
        local = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            "monitor_server",
            self.parameters["scpi_server_name"],
        )
        with open(local, "rb") as binary:
            local_md5 = hashlib.md5(binary.read()).hexdigest()
        remote = self._ssh_exec(f"md5sum {self._scpi_server_path()}")
        if local_md5 in remote and not self.parameters["reloadserver"]:
            return
        self.endscpiserver()
        # rw/ro remount the file system on OS versions that mount it read-only
        path = "PATH=$PATH:/opt/redpitaya/sbin:/opt/redpitaya/bin; "
        self._ssh_exec(
            path + "command -v rw >/dev/null && rw; mkdir -p " + self.parameters["serverdirname"]
        )
        self.put_file(local, self._scpi_server_path())
        self._ssh_exec(
            path + f"chmod 755 {self._scpi_server_path()}; command -v ro >/dev/null && ro"
        )
        self.logger.debug("SCPI server installed at %s", self._scpi_server_path())

    def startscpiserver(self):
        """Starts the read-only SCPI server (parameter scpi_server=True).

        The server runs in the background and survives the end of this PyRPL
        session, so that other acquisition programs keep their connection. It
        is only restarted when its settings change, and always stopped before
        the FPGA is reprogrammed."""
        if not self.parameters["scpi_server"] or not hasattr(self, "ssh"):
            return
        self.installscpiserver()
        command = self._scpi_server_command()
        if command in self._scpi_server_cmdline():
            self.logger.debug("SCPI server already running: %s", command)
            return
        self.endscpiserver()
        # the stock SCPI server uses the same port and writes to the FPGA
        # registers of the stock image, which would disturb PyRPL
        self._ssh_exec("systemctl stop redpitaya_scpi")
        log = f"/tmp/{self.parameters['scpi_server_name']}.log"
        self._ssh_exec(f"nohup {command} > {log} 2>&1 < /dev/null &")
        sleep(10 * self.parameters["delay"])
        if command in self._scpi_server_cmdline():
            self.logger.info(
                "Read-only SCPI server listening on %s:%d",
                self.parameters["hostname"],
                self.parameters["scpi_port"],
            )
        else:
            self.logger.error(
                "The SCPI server could not be started: %s", self._ssh_exec(f"cat {log}")
            )

    def endscpiserver(self):
        """Stops the SCPI server and all its client connections."""
        if not hasattr(self, "ssh"):
            return
        self._ssh_exec("killall " + self.parameters["scpi_server_name"])
        sleep(self.parameters["delay"])

    def endclient(self):
        del self.client
        self.client = None

    def start(self):
        if self.parameters["leds_off"]:
            if (
                self.os_version.find("2.") != -1 or self.os_version.find("3.") != -1
            ):  # for os > 1.0x
                self.ssh.ask("\x03")
                self.ssh.ask("/opt/redpitaya/bin/led_control -y=Off -e=Off -r=Off")
            else:  # for os <= 1.0x
                self.switch_led(gpiopin=0, state=False)
                self.switch_led(gpiopin=7, state=False)
        # read-only SCPI server for other acquisition programs (scpi_server=True)
        self.startscpiserver()
        self.startserver()
        sleep(self.parameters["delay"])
        self.startclient()

    def end(self):
        self.endserver()
        self.endclient()

    def end_ssh(self):
        if hasattr(self, "ssh"):
            self.ssh.channel.close()

    def end_all(self):
        self.end()
        self.end_ssh()

    def restart(self):
        self.end()
        self.start()

    def restartserver(self, port=None):
        """restart the server. usually executed when client encounters an error"""
        if port is not None:
            if port < 0:  # code to try a random port
                self.parameters["port"] = random.randint(2223, 50000)
            else:
                self.parameters["port"] = port
        return self.startserver()

    def license(self):
        self.logger.info("""\r\n    pyrpl  Copyright (C) 2014-2017 Leonhard Neuhaus
    This program comes with ABSOLUTELY NO WARRANTY; for details read the file
    "LICENSE" in the source directory. This is free software, and you are
    welcome to redistribute it under certain conditions; read the file
    "LICENSE" in the source directory for details.\r\n""")

    def startclient(self):
        self.client = redpitaya_client.MonitorClient(
            self.parameters["hostname"],
            self.parameters["port"],
            restartserver=self.restartserver,
        )
        self.makemodules()
        self._validate_fpga_profile()
        self.logger.debug("Client started successfully. ")

    def startdummyclient(self):
        self.client = redpitaya_client.DummyClient(self.fpga_profile)
        self.makemodules()
        self._validate_fpga_profile()

    def makemodule(self, name, cls):
        module = cls(self, name)
        for attribute, value in self.fpga_profile.module_attributes(cls.__name__).items():
            setattr(module, attribute, value)
        if cls.__name__ == "Pid" and "pid_derivative" in self.fpga_profile.capabilities:
            derivative_attributes = ["d", "derivative_filter_ratio"]
            for attribute_list_name in ("_setup_attributes", "_gui_attributes"):
                attributes = list(getattr(module, attribute_list_name))
                insertion_index = attributes.index("i") + 1
                attributes[insertion_index:insertion_index] = derivative_attributes
                setattr(module, attribute_list_name, attributes)
        if cls.__name__ == "Pid" and "pid_external_pause" in self.fpga_profile.capabilities:
            pause_attributes = ["pause_source", "pause_pin"]
            for attribute_list_name in ("_setup_attributes", "_gui_attributes"):
                attributes = list(getattr(module, attribute_list_name))
                insertion_index = attributes.index("paused") + 1
                attributes[insertion_index:insertion_index] = pause_attributes
                setattr(module, attribute_list_name, attributes)
        setattr(self, name, module)
        self.modules[name] = module

    def _validate_fpga_profile(self):
        """Reject a Python profile that does not match the loaded register map."""
        expected = self.fpga_profile.hardware
        observed = {}
        if hasattr(self, "iir"):
            observed.update(
                iir_bits=self.iir._IIRBITS,
                iir_shift=self.iir._IIRSHIFT,
                iir_stages=self.iir._IIRSTAGES,
            )
        if hasattr(self, "pid0"):
            observed["pid_input_filter_stages"] = self.pid0._read(0x220)
            if "pid_derivative" in expected:
                observed["pid_derivative"] = self.pid0._read(0x210)
        if hasattr(self, "cordic") and "cordic_abi" in expected:
            observed["cordic_abi"] = self.cordic.abi_version
        mismatches = {
            key: (expected[key], observed[key])
            for key in expected
            if key in observed and expected[key] != observed[key]
        }
        if mismatches:
            details = ", ".join(
                f"{key}: expected {values[0]}, read {values[1]}"
                for key, values in mismatches.items()
            )
            raise RuntimeError(
                f"Loaded FPGA does not match profile {self.fpga_profile.id!r}: {details}"
            )

    def makemodules(self):
        """
        Automatically generate modules declared by the selected FPGA profile.
        """
        names = get_unique_name_list_from_class_list(self.cls_modules)
        for cls, name in zip(self.cls_modules, names):
            self.makemodule(name, cls)

    def make_a_slave(self, port=None, monitor_server_name=None, gui=False):
        if port is None:
            port = self.parameters["port"] + len(self._slaves) * 10 + 1
        if monitor_server_name is None:
            monitor_server_name = self.parameters["monitor_server_name"] + str(port)
        slaveparameters = dict(self.parameters)
        slaveparameters.update(
            dict(
                port=port,
                autostart=True,
                reloadfpga=False,
                reloadserver=False,
                monitor_server_name=monitor_server_name,
                silence_env=True,
            )
        )
        r = RedPitaya(**slaveparameters)  # gui=gui)
        r._master = self
        self._slaves.append(r)
        return r
