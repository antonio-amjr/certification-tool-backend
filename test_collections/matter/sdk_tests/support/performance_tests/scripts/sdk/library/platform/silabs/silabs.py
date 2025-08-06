#
#
#  Copyright (c) 2023 Project CHIP Authors
#
#  Licensed under the Apache License, Version 2.0 (the 'License');
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an 'AS IS' BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import time
import logging
from threading import Event, Thread
from matter_qa.library.base_test_classes.dut_base_class import BaseDutNodeClass
from matter_qa.library.helper_libs.telnet import TelnetClient
import re
import traceback
from typing import Union

event_closer = Event()


class SilabsDUT(BaseDutNodeClass):
    def __init__(self, test_config) -> None:
        super().__init__()
        self.dut_config = test_config.dut_config.silabs
        self.test_config = test_config

        self.telnet_client = TelnetClient(self.dut_config.telnet_remote,
                                          self.dut_config.telnet_port,
                                          self.dut_config.telnet_timeout)
        self.expected: Union[str, bytes, re.Pattern] = re.compile(b'WSTK> |WPK>')

    def start_test(self, *args, **kwargs):
        pass

    def reboot_dut(self, *args, **kwargs):
        pass

    def factory_reset_dut(self, *args, **kwargs):
        try:
            self.telnet_client.write_expect('target button disable 0', expected=self.expected)
            self.telnet_client.write_expect('target button enable 0', expected=self.expected)
            self.telnet_client.write_expect('target button press 0', expected=self.expected)
            time.sleep(10)
            self.telnet_client.write_expect('target button release 0', expected=self.expected)
        except Exception as e:
            logging.error(e)
            traceback.print_exc()

    def start_matter_app(self, *args, **kwargs):
        try:
            self.factory_reset_dut()
        except Exception as e:
            logging.error(e)
            traceback.print_exc()

    def start_logging(self, file_name, *args, **kwargs):
        pass

    def stop_logging(self, *args, **kwargs):
        pass

    def pre_iteration_loop(self, *args, **kwargs):
        pass

    def post_iteration_loop(self, *args, **kwargs):
        pass

    def end_test(self, *args, **kwargs):
        pass