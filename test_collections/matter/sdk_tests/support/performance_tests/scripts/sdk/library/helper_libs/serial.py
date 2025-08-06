import logging
from matter_qa.library.helper_libs.logger import qa_logger
import sys
from serial import Serial
from matter_qa.library.helper_libs.exceptions import SerialConnectionError
from mobly import signals


log = logging.getLogger("serial")
log.propagate = True
class SerialConfig:
    """
    Configuration class for serial communication settings.

    Attributes:
        serial_port (str): The port used for serial communication.
        baudrate (int): The baud rate for the connection.
        timeout (float): Timeout value for serial communication.
    """
    def __init__(self, serial_port, baudrate, timeout) -> None:
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.timeout = timeout

class SerialConnection:
    def __init__(self, serial_config):
        self.port = serial_config.serial_port
        self.baudrate = serial_config.baudrate
        self.timeout = serial_config.timeout

        try:
            self.serial_object = Serial(self.port, self.baudrate, timeout=self.timeout)
        except Exception as e:
            raise signals.TestAbortAll(f"could not connect to Nordic DUT: {e}")
            

    def send_command(self, command):
        try:
            self.serial_object.write(command)
            self.serial_object.flush()
        except Exception as e:
            log.error(e, exc_info=True)
            raise SerialConnectionError(str(e))

    def open_serial_connection(self):
        try:
            if not self.serial_object.is_open:
                logging.info("Opening Serial Port")
                self.serial_object.open()
        except Exception as e:
            log.error(e, exc_info=True)
            raise SerialConnectionError(str(e))


    def close_serial_connection(self):
        try:
            self.serial_object.close()
        except Exception as e:
            log.error(e, exc_info=True)
            raise SerialConnectionError(str(e))
