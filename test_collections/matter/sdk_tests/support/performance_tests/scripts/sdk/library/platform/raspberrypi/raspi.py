#
#
#  Copyright (c) 2023 Project CHIP Authors
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import datetime
import logging
import os
import shlex
import threading
import time
import io
import yaml

from matter_qa.library.base_test_classes.dut_base_class import BaseDutNodeClass
from matter_qa.library.helper_libs.capture import TCPDumpCapture, BluezCapture, DBusCapture, HCIDumpCapture, WPASupplicantCapture
from matter_qa.library.helper_libs.exceptions import DUTInteractionError
from matter_qa.library.helper_libs.ssh import SSH, SSHConfig, CallbackStream

global log
log = logging.getLogger("raspi")
log.propagate = True

PID_FILE = "/tmp/tcpdump_pid.txt"


class Raspi(BaseDutNodeClass):
    """
    A class representing a Raspberry Pi (RPI) device as a Device Under Test (DUT).
    It provides functionality to interact with the RPI via SSH for operations such as
    reboot, factory reset, log capture, and tcpdump management.
    """

    def __init__(self, test_config) -> None:
        """
        Initializes the Raspi class and establishes SSH sessions.

        - param test_config: The configuration object containing RPI-related settings.
        """
        super().__init__()
        self.dut_config = test_config.dut_config.rpi
        ssh_config = SSHConfig(
            test_config.dut_config.rpi.rpi_hostname,
            test_config.dut_config.rpi.rpi_username,
            test_config.dut_config.rpi.rpi_password,
            test_config.dut_config.rpi.rpi_sudo_password
        )
        # SSH sessions object of dut
        self.matter_app_ssh_session = SSH(ssh_config)
        self.matter_app = self._build_app_cmd_string(self.dut_config.app_config)
        self.test_config = test_config
        self.write_log = False
        # Lock to synchronize log content access
        self.log_lock = threading.Lock()
        # Default values for additional configurations
        if not hasattr(self.test_config.dut_config.rpi, "download_var_logs"):
            setattr(self.test_config.dut_config.rpi, "download_var_logs", False)
        if not hasattr(self.test_config.dut_config.rpi, "delay_after_factory_reset"):
            setattr(self.test_config.dut_config.rpi, "delay_after_factory_reset", 5)
        self.delay_after_factory_reset = getattr(self.test_config.dut_config.rpi, "delay_after_factory_reset", 5)

        self.captures = []
        if getattr(self.test_config.dut_config.rpi, 'capture_bluez', True):
            self.captures.append(BluezCapture("RPI-DUT", self.matter_app_ssh_session))
        if getattr(self.test_config.dut_config.rpi, 'capture_hcidump', True):
            self.captures.append(HCIDumpCapture("RPI-DUT", self.matter_app_ssh_session))
        if getattr(self.test_config.dut_config.rpi, 'capture_tcpdump', True):
            self.captures.append(TCPDumpCapture("RPI-DUT", self.matter_app_ssh_session))
        if getattr(self.test_config.dut_config.rpi, 'capture_dbus', True):
            self.captures.append(DBusCapture("RPI-DUT", self.matter_app_ssh_session))
        if getattr(self.test_config.dut_config.rpi, 'capture_wpasupplicant', True):
            self.captures.append(WPASupplicantCapture("RPI-DUT", self.matter_app_ssh_session))

    def _get_app_cmd_dict_from_file(self):
        """
            function reads ~/stresstest/dutconfig/raspi_config.yaml if it exits
            otherwise pass
        """
        try:
            relative_path = os.path.join("MatterSDK_stresstest", "dutconfig", "raspi", "raspi_config.yaml")
            full_file_path = os.path.expanduser(os.path.join("~", relative_path))
            with io.open(full_file_path, 'r') as f:
                test_config_dict = yaml.safe_load(f)
            return test_config_dict
        except Exception as e:
            pass

    def _update_class_attributes(self, app_config, dict_config):
        for key, value in dict_config.items():
            if type(value) is not dict:
                if hasattr(app_config, key):
                    setattr(app_config, key, value)
            else:
                self._update_class_attributes(app_config, value)

    def _app_cmd_string(self, app_config):
        attributes = vars(app_config)
        app_cmd = ""
        for k, v in attributes.items():
            if k == "matter_app":
                app_cmd = app_cmd + v
            else:
                app_cmd = app_cmd + " " + "--" + k + " " + str(v)

        return app_cmd

    def _build_app_cmd_string(self, app_dict):
        app_cmd_dict_from_file = self._get_app_cmd_dict_from_file()
        if app_cmd_dict_from_file is not None:
            self._update_class_attributes(self.dut_config.app_config, app_cmd_dict_from_file)

        return self._app_cmd_string(self.dut_config.app_config)

    def start_test(self, *args, **kwargs):
        """
        Initiates the test process by establishing SSH connections to the required devices or systems.

        This method performs the following steps:
        - Opens an SSH connection to the Matter application server.
        - Opens an SSH connection to the DUT (Device Under Test) for tcpdump operations.

        Raises:
            SystemExit: If any SSH connection fails, the program will exit with a status code of 1.

        Notes:
            This method ensures that all required SSH sessions are initialized before any test steps are executed.
        """
        try:
            # Establish SSH connections
            self.matter_app_ssh_session.open()
            self._delete_storage()
        except Exception as e:
            raise DUTInteractionError(f"Could not establish SSH connection: {e}", exc_info=True)

    def reboot_dut(self, *args, **kwargs):
        """
        Reboots the DUT by stopping the app, restarting the SSH session,
        and restarting the sample app.

        raises DUTInteractionError: If the reboot process fails.
        """
        try:
            self._kill_app()
            time.sleep(5)
            log.info("Example App has been killed")
            self._start_matter_app()
            return True
        except Exception as e:
            log.error(f"Failed to reboot DUT:{e}", exc_info=True)
            raise DUTInteractionError(f"Failed to reboot the dut :{e}")

    def factory_reset_dut(self, *args, **kwargs) -> None:
        """
        Performs a factory reset on the DUT by stopping the app, deleting
        temporary storage, and restarting the sample app.
        """
        try:
            log.info("Removing any existing DUT instance(Example/sample app kill) before launching the app")
            # Executing the  'ps aux | grep process_name' command to find the PID value to kill
            self._kill_app()
            log.info("Starting to factory reset RPI as the DUT")
            self._delete_storage()
            self._start_matter_app()
            log.info("Delaying execution to make DUT advertising efficient")
            time.sleep(self.delay_after_factory_reset)
        except Exception as e:
            log.error(f"Factory reset failed:{e}", exc_info=True)

    def _kill_app(self):
        """
        Kills the running sample app on the DUT by finding its PID and terminating it.

        raises DUTInteractionError: If the app cannot be terminated.
        """
        try:
            def get_sample_app_name():
                """
                This function is to extract the app name from the mmatteer app command
                """
                if not self.matter_app:
                    raise DUTInteractionError("Matter app must be defined in config file before running this test.")

                    # Use shlex to split properly even if arguments are quoted
                parts = shlex.split(self.matter_app)

                if not parts:
                    raise DUTInteractionError("Matter app must be defined in config file before running this test.")

                # First part is expected to be the binary path
                matter_app_path = parts[0].rstrip("/")  # Remove any trailing slash

                return os.path.basename(matter_app_path)

            sample_app_name = get_sample_app_name()
            command = f'pidof "{sample_app_name}"'
            pidof_val = self.matter_app_ssh_session.run(command, timeout=30, hide=True, warn=True)
            if pidof_val:
                list_of_pid = pidof_val.stdout.split(' ')
                for pid in list_of_pid:
                    log.info(f"Terminating process: {pid}")
                    kill_command = f"kill {pid}"
                    self.matter_app_ssh_session.run(kill_command, timeout=30)
        except Exception as e:
            log.error(f"Failed to kill app:{e}", exc_info=True)
            raise DUTInteractionError(f"Failed to kill app: {e}")

    def _delete_storage(self):
        """
        Deletes temporary storage files on the DUT.
        """
        try:
            self.matter_app_ssh_session.run('rm -rf /tmp/chip_*')
        except Exception as e:
            log.error(f"Failed to delete storage:{e}", exc_info=True)

    def start_matter_app(self, *args, **kwargs):
        """
        Starts _start_matter_app function .
        """
        self._start_matter_app()

    def _start_matter_app(self):
        """
        Starts the sample app and initiates a log capture thread.

        raises DUTInteractionError: If the app cannot be started.
        """
        try:
            self.log_thread = threading.Thread(target=self._capture_log)
            self.log_thread.daemon = True
            self.log_thread.start()
        except Exception as e:
            log.error(f"Failed to start Matter app:{e}", exc_info=True)
            raise DUTInteractionError(f"Failed to start the matter app {e}")

    def _capture_log(self) -> None:
        """
        Captures logs from the DUT and writes them to a log file.

        raises DUTInteractionError: If log collection fails.
        """
        try:
            def log_callback(data):
                if self.write_log:
                    with open(self.log_file, "a") as file:
                        file.write(data)
                        file.flush()
            self.matter_app_ssh_session.run(self.matter_app, out_stream=CallbackStream(log_callback),
                                            warn=True, hide=True, pty=True)
        except Exception as e:
            log.error(f"Failed to collect log output:{e}", exc_info=True)
            raise DUTInteractionError(f"Failed to collet lo from the matter app {e}")

    def start_logging(self, file_name=None, *args, **kwargs) -> None:
        """
        Starts logging output to a specified file

        Args:
            file_name (str): The name of the file to write the logs to.
        """
        if file_name:
            self.log_file = file_name
        else:
            self.log_file = os.path.join(
                self.test_config.iter_log_path,
                f"Dut_log_iteration_{self.test_config.current_iteration}_"
                f"{datetime.datetime.now().isoformat().replace(':', '_').replace('.', '_')}.log")
        self.write_log = True
        with open(self.log_file, "a") as file:
            file.write(f"\n\nDut log of iteration {self.test_config.current_iteration}\n")

    def stop_logging(self, *args, **kwargs):
        """
        Stops logging by disabling the log writing flag.
        This ensures no further logs will be written to the file.
        """
        self.write_log = False

    def _download_var_logs(self):
        """
        Downloads the var log files from the DUT under the /var/log directory. This is done only when
        the configuration specifies to download the logs and the current iteration matches the failed iteration.

        The method performs the following:
        - Verifies if the download of log files is enabled in the configuration.
        - Creates a local directory to store the logs.
        - Downloads each log file specified in the configuration.
        """
        if self.test_config.dut_config.rpi.download_var_logs is True and self.test_config.current_iteration == self.test_config.current_failed_iteration:
            remote_file_path = "/var/log"
            var_log_filenames = self.test_config.dut_config.rpi.var_log_filenames
            dut_var_logs_path = os.path.join(self.test_config.iter_log_path, "dut_var_logs")
            try:
                # Create the directory to store the downloaded logs if it does not exist
                if not os.path.exists(dut_var_logs_path):
                    os.mkdir(dut_var_logs_path)
                # Iterate over each log file specified in the configuration
                for var_log_filename in var_log_filenames:
                    try:
                        host_file_full_name = os.path.join(dut_var_logs_path, var_log_filename)
                        remote_file_full_name = os.path.join(remote_file_path, var_log_filename)
                        self.matter_app_ssh_session.get(remote_file_full_name, host_file_full_name)
                        log.info(f"Downloaded {remote_file_full_name} to {host_file_full_name}")
                    except FileNotFoundError:
                        log.error(f"{remote_file_full_name} does not exist on the server.", exc_info=True)
                    except Exception as e:
                        log.error(f"Failed to download var log files: {e}", exc_info=True)
            except Exception as e:
                log.error(f"Failed to download var log files: {e}", exc_info=True)

    def pre_iteration_loop(self, *args, **kwargs):
        """
        Execute before the each iteration starts. This includes starting logging for the iteration and initiating
        tcpdump capture to monitor network traffic during the test.

        This method performs the following steps:
        - Starts logging to a file named with the current iteration and timestamp.
        - Starts capturing network traffic with tcpdump.
        """
        self.start_logging()
        for capture in self.captures:
            capture.start()

    def post_iteration_loop(self, *args, **kwargs):
        """
        Execute after the each iteration ends. This includes stopping logging, stopping the tcpdump capture,
        and downloading logs and tcpdump data from the DUT.

        This method performs the following:
        - Stops logging the iteration output.
        - Stops the tcpdump capture process.
        - Downloads the tcpdump capture file and removes it from the DUT.
        - Downloads the system logs from the DUT, if the current iteration is the failed one.
        """
        self.stop_logging()
        self._download_var_logs()
        for capture in self.captures:
            capture.stop()
            file = capture.get_capture_file(self.test_config.iter_log_path)
            log.info(f"Downloaded capture file: {file}")

    def end_test(self, *args, **kwargs):
        """
        Execute at the ends of the test to cleaning up resources and closing connections.

        This includes:
        - Killing any running application processes.
        - Deleting storage data.
        - Closing the SSH session.
        """
        try:
            self._kill_app()
            self._delete_storage()
            self.matter_app_ssh_session.close()
        except Exception as e:
            log.error(f"Failed to end the test: {e}", exc_info=True)
