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
import time
import logging
import os
from threading import Event, Thread
import sys
from matter_qa.library.base_test_classes.dut_base_class import BaseDutNodeClass
from matter_qa.library.helper_libs.serial import SerialConnection, SerialConfig
from matter_qa.library.helper_libs.exceptions import DUTInteractionError

global log
log = logging.getLogger("nordic")
log.propagate = True

event_closer = Event()  # flag used to keep trace of start/stop of capturing the DUT log


class NordicDut(BaseDutNodeClass):
    """
    Represents a Nordic DUT (Device Under Test) with functionalities 
    for serial communication, logging, and test management.

    """
    def __init__(self, test_config, *args, **kwargs) -> None:
        """
        Initialize the Nordic DUT instance with necessary configurations.

        Args:
            test_config: Configuration object containing DUT and test settings.
        """
        super().__init__()
        self.dut_config = test_config.dut_config.nordic
        self.serial_config = SerialConfig(test_config.dut_config.nordic.serial_port,
                                     test_config.dut_config.nordic.serial_baudrate,
                                     test_config.dut_config.nordic.serial_timeout)
        self.serial_session = SerialConnection(self.serial_config)
        self.factoryreset_command = self.dut_config.factoryreset_command
        self.test_config = test_config
                 
    
    def start_test(self, *args, **kwargs):
        """
        Starts the test by establishing a serial connection to the DUT.
        Exits the program if the connection fails.
        """
        try:
            self.serial_session.open_serial_connection()
        except Exception as e:
            raise DUTInteractionError(f"Could not establish Serial connection {e}" , exc_info=True)

    def reboot_dut(self, *args, **kwargs):
        """
        Reboots the DUT by stopping the app 
        """
        pass

    def start_matter_app(self, *args, **kwargs):
        """
        Start the Matter application on the DUT. To be implemented if necessary.
        """
        pass

    def factory_reset_dut(self, *args, **kwargs):
        """
        Performs a factory reset on the DUT by sending reset commands.
        Handles serial port operations and ensures the DUT is reset properly.
        """
        try:
            for iteration in range(1, 3):
                try:
                    log.info(f"Starting to Reset Nordic as the DUT {iteration}")
                    if self.serial_session.serial_object.is_open:  # directly send reset command if port is opened
                        self.serial_session.send_command(self.factoryreset_command.encode('utf-8'))
                        time.sleep(5)  # we have to wait for a minimum of 4 seconds for the dut to be in advertising mode
                    else:  # send reset command only after opening the port
                        self.serial_session.open_serial_connection()
                        self.serial_session.send_command(self.factoryreset_command.encode('utf-8'))
                        time.sleep(5)  # we have to wait for a minimum of 4 seconds for the dut to be in advertising mode
                except Exception as e:
                    log.error(f"Failed to Reset Nordic as the DUT {iteration}:{e}", exc_info=True)
            event_closer.set()  # set the flag to stop capturing the DUT LOGS
            self.serial_session.close_serial_connection()
            log.info("Reset Completed")
        except Exception as e:
            log.error(f"Failed to Factory reset the dut: {e}", exc_info=True)

    def start_logging(self, file_name = None, *args, **kwargs):
        """
        Starts logging DUT output by initiating a separate thread.
        """
        try:
            event_closer.clear()  # setting the flag to bool 'False' value to start capturing the DUT logs
            thread = Thread(target=self._start_logging)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            log.error(f"Failed to capture the log:{e}", exc_info=True)

    def _start_logging(self, file_name = None):
        """
        Internal method to read logs from the DUT and save them to a file.

        Args:
            file_name (str, optional): Name of the log file to save output.
        """
        try:
            # open serial connection when port is closed for reading dut logs via serial interface
            # Create a new serial object to avoid thread conflicts.
            self.serial_session_read_logs = SerialConnection(self.serial_config)
            if not self.serial_session_read_logs.serial_object.is_open:
                self.serial_session_read_logs.open_serial_connection()
            if self.serial_session_read_logs.serial_object.is_open:
                if event_closer.is_set():  # here we check the flag to see if iteration has ended
                    return True
                log_file = os.path.join(self.test_config.iter_log_path, "Dut_log_{}_"
                                        .format(str(self.test_config.current_iteration)) +
                                        str(datetime.datetime.now().isoformat()).replace(':', "_")
                                        .replace('.', "_") + ".log")  # build DUT log file name
                logging.info("started to read buffer")
                #  we will read from DUT until we get the unique termination string 'Done'
                dut_log = self.serial_session_read_logs.serial_object.read_until(b'stop_logging').decode()
                logging.info("completed read from buffer")
                with open(log_file, 'w') as fp:
                    fp.write(f" \n\n  Dut log of {self.test_config.current_iteration} iteration \n")
                    fp.write(dut_log)
                    logging.info(f"completed write to file for iteration {self.test_config.current_iteration}")
                if dut_log == '':
                    log.info("data not present in buffer leaving read operation")
                    return True
            self.serial_session_read_logs.close_serial_connection()
            return True
        except Exception as e:
            log.error(f"Failed to capture the log:{e}", exc_info=True)
            raise DUTInteractionError(f"Failed to save the log: {e}")

    def _stop_logging(self, *args, **kwargs):
        """
        Stops logging DUT output by signaling the DUT and closing the serial port.
        """
        try:
            if self.serial_session.serial_object.is_open:
                self.serial_session.send_command(b'\n stop_logging \n')
                time.sleep(5)
            else:
                self.serial_session.open_serial_connection()
                self.serial_session.send_command(b'\n stop_logging \n')
                time.sleep(5)
            event_closer.set()
            self.serial_session.close_serial_connection()
        except Exception as e:
            log.error(f"Failed to stop the log:{e}", exc_info=True)
    
    def stop_logging(self, *args, **kwargs):
        self._stop_logging(args,kwargs)

    def pre_iteration_loop(self, *args, **kwargs):
        """
        Prepares the DUT for each test iteration by starting the logging process.
        """
        self.start_logging()

    def post_iteration_loop(self, *args, **kwargs):
        """
        Cleans up after each test iteration by stopping the logging process.
        """
        self.stop_logging()

    def end_test(self, *args, **kwargs):
        """
        Ends the test and ensures the serial connection is closed properly.
        """
        try:
            if self.serial_session.serial_object.is_open:
                self.serial_session.close_serial_connection()
        except Exception as e:
            log.error(f"Failed to end the test: {e}", exc_info=True)