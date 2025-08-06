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
import threading
import time
import io
import re
import yaml
from types import SimpleNamespace

from matter_qa.library.base_test_classes.dut_base_class import BaseDutNodeClass
from matter_qa.library.helper_libs.exceptions import DUTInteractionError
from .connector import create_connector

log = logging.getLogger(__name__)


class Tizen(BaseDutNodeClass):
    """
    A class representing a Tizen device as a Device Under Test (DUT).
    It provides functionality to interact with the Tizen via SDB or SSH for
    operations such as reboot, factory reset, and log capture.
    """

    def __init__(self, test_config) -> None:
        """
        Initializes the Tizen class and establishes SSH sessions.

        - param test_config: The configuration object the test config.
        """
        super().__init__()
        self.test_config = test_config
        self.dut_config = test_config.dut_config.tizen
        self.connector = create_connector(self.dut_config)
        self.captures = []  # Captures not supported yet

        def set_default(obj, attr, value):
            """Helper function to set default attribute if missing."""
            if not hasattr(obj, attr):
                setattr(obj, attr, value)

        self.app_args = ' '.join([ f"{k} {str(v)}" for k,v in vars(self.dut_config.app_config).items() ])

        set_default(self.dut_config, "delay_after_factory_reset", 5)

        set_default(self.dut_config, 'factory_reset', SimpleNamespace())
        set_default(self.dut_config.factory_reset, 'clear_connman_state', True)
        # Bluez state clear commands break GATT registration
        set_default(self.dut_config.factory_reset, 'clear_bluetoothd_state', False)


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
            self.connector.open()
            self._delete_storage()
        except Exception as e:
            raise DUTInteractionError(f"Could not start test: {e}", exc_info=True)

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


    def _clear_connman_state(self):
        """
        Remove all configured WiFi services.
        """
        res = self.connector.sudo('connmanctl services')
        lines = res.stdout.split('\n')
        for line in lines:
            m = re.match(r'(?P<favorite_flag>[* ])'
                         r'(?P<autoconnectable_flag>[A ])'
                         r'(?P<state_flag>[OR])\s+'
                         r'(?P<name>\w+)\s+'
                         r'(?P<service_id>\w+)', line)
            if m:
                service_id = m.group('service_id')
                if m.group('favorite_flag') == '*' and service_id.startswith('wifi_'):
                    log.debug(f"Removing connman service '{service_id}'")
                    self.connector.sudo('gdbus call --system --dest net.connman '
                                       f"--object-path '/net/connman/service/{service_id}' "
                                        '--method net.connman.Service.Remove')


    def _clear_bluetoothd_state(self):
        self.connector.sudo('systemctl stop bluez-start.service')
        # Remove only files which are created for connected Bluetooth devices.
        self.connector.sudo('rm -rf /var/lib/bluetooth/'
                            '[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:'
                            '[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:'
                            '[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]')
        self.connector.sudo('systemctl start bluez-start.service')


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

            if self.dut_config.factory_reset.clear_connman_state:
                self._clear_connman_state()
            if self.dut_config.factory_reset.clear_bluetoothd_state:
                self._clear_bluetoothd_state()

            self._start_matter_app()
            log.info("Delaying execution to make DUT advertising efficient")
            time.sleep(self.dut_config.delay_after_factory_reset)
        except Exception as e:
            log.error(f"Factory reset failed: {e}", exc_info=True)
            raise DUTInteractionError(f"Factory reset disabled: {e}")

    def _kill_app(self):
        """
        Kills the running sample app on the DUT by finding its PID and terminating it.

        raises DUTInteractionError: If the app cannot be terminated.
        """
        try:
            log.info(f"Stopping DUT app '{self.dut_config.app_package_id}'")
            status = self.connector.app_status(self.dut_config.app_package_id)
            if status.running is True:
                self.connector.stop_app(self.dut_config.app_package_id)
        except Exception as e:
            raise DUTInteractionError(f"Failed to kill app '{self.dut_config.app_package_id}': {e}")

    def _delete_storage(self):
        """
        Deletes temporary storage files on the DUT.
        """
        try:
            log.info(f"Clearing data for app '{self.dut_config.app_package_id}'")
            self.connector.run(f"pkgcmd -c -t tpk -n '{self.dut_config.app_package_id}'")
        except Exception as e:
            log.error(f"Failed to delete storage: {e}", exc_info=True)

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

        # We don't need a thread to watch the log, dlog provides this feature for us
        # Todo: run dlogutil
        log.info(f"Starting app '{self.dut_config.app_package_id}'")
        self.connector.run(f"app_launcher -s '{self.dut_config.app_package_id}' -- {self.app_args}")

    def start_logging(self, file_name=None, *args, **kwargs) -> None:
        """
        Starts logging output to a specified file

        Args:
            file_name (str): The name of the file to write the logs to.
        """
        # Logging is always possible with dlog
        pass

    def stop_logging(self, *args, **kwargs):
        """
        Stops logging by disabling the log writing flag.
        This ensures no further logs will be written to the file.
        """
        pass


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
            self.connector.close()
        except Exception as e:
            log.error(f"Failed to end the test: {e}", exc_info=True)
