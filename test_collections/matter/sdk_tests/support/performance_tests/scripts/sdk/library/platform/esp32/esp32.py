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
from matter_qa.library.helper_libs.serial import SerialConnection

global log
log = logging.getLogger("esp32")
event_closer = Event()  # flag used to keep trace of start/stop of capturing the DUT log


class SerialConfig:
    def __init__(self, serial_port, baudrate, timeout) -> None:
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.timeout = timeout

class Esp32Dut(BaseDutNodeClass):
    def __init__(self, test_config, *args, **kwargs) -> None:
        super().__init__()
        self.dut_config = test_config.dut_config.esp32
        serial_config = SerialConfig(test_config.dut_config.esp32.serial_port,
                                     test_config.dut_config.esp32.serial_baudrate,
                                     test_config.dut_config.esp32.serial_timeout)
        self.serial_session = SerialConnection(serial_config)
        self.command = self.dut_config.command
        self.test_config = test_config

    def start_test(self, *args, **kwargs):
        try:
            self.serial_session.open_serial_connection()
        except Exception as e:
            log.error("Could not establish Serial connection {}".format(e))
            sys.exit(1)
    def factory_reset_dut(self, *args, **kwargs):
        try:
            for iteration in range(1, 3):
                if not self.serial_session.serial_object.is_open:
                    self.serial_session.open_serial_connection()
                
                log.info(f"Starting to Reset Esp32 as the DUT {iteration}")
                self.serial_session.send_command(self.command.encode('utf-8'))
                time.sleep(5)
            event_closer.set()
            self.serial_session.close_serial_connection()
            log.info("Reset Completed")
        except Exception as e:
            log.error(e, exc_info=True)

    def reboot_dut(self, *args, **kwargs):
        pass

    def start_matter_app(self, *args, **kwargs):
        pass

    def start_logging(self, file_name=None, *args, **kwargs):
        event_closer.clear()  # setting the flag to bool 'False' value to start capturing the DUT logs
        thread = Thread(target=self._start_logging)
        thread.start()

    def _start_logging(self, file_name=None):
        # Ensure the serial connection is open
        if not self.serial_session.serial_object.is_open:
            self.serial_session.open_serial_connection()
            
        if self.serial_session.serial_object.is_open:
            try:
                if event_closer.is_set():
                    return True
                
                # Construct the log file name
                log_file = os.path.join(
                    self.test_config.iter_log_path,
                    f"Dut_log_{self.test_config.current_iteration}_{datetime.datetime.now().isoformat().replace(':', '_').replace('.', '_')}.log"
                )
                
                logging.info("Started to read buffer")
                
                # Read from DUT until the termination string 'Done' is encountered
                dut_log = self.serial_session.serial_object.read_until(b'Done').decode()
                
                logging.info("Completed read from buffer")
                
                with open(log_file, 'w') as fp:
                    fp.write(f"\n\nDut log of {self.test_config.current_iteration} iteration\n")
                    fp.write(dut_log)
                    
                logging.info(f"Completed write to file for iteration {self.test_config.current_iteration}")
                
                if not dut_log.strip():
                    logging.info("Data not present in buffer; leaving read operation")
                    
                return True
                
            except Exception as e:
                log.error(e, exc_info=True)
                
        self.serial_session.close_serial_connection()
        return True

    def stop_logging(self, *args, **kwargs):
        if not self.serial_session.serial_object.is_open:
            self.serial_session.open_serial_connection()

        try:
            self.serial_session.send_command(b'Done')
            event_closer.set()
        except Exception as e:
            log.error(f"Error while sending command to stop logging: {e}", exc_info=True)

        with self.serial_session.serial_object:
            self.serial_session.close_serial_connection()

    def pre_iteration_loop(self, *args, **kwargs):
        self.start_logging()

    def post_iteration_loop(self, *args, **kwargs):
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