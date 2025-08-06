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

import logging
import re
import traceback
from telnetlib import Telnet
from typing import Optional, Union


class TelnetClient(object):
    def __init__(self, remote, port, timeout) -> None:
        self.remote = remote
        self.port = port
        self.timeout = timeout
        self.telnet_client = Telnet(host=self.remote, port=self.port, timeout=self.timeout)

    def write_cmd(self, cmd):
        if isinstance(cmd, str):
            cmd = cmd.encode() + "\r\n".encode()
        try:
            self.telnet_client.write(cmd)
        except Exception as e:
            logging.error(e)
            traceback.print_exc()

    def read_expect(
        self,
        expected: Union[str, bytes, re.Pattern] = None,
        timeout: Optional[float] = 1):
        if expected is None:
            raise NotImplementedError()
        if isinstance(expected, str):
            expected = expected.encode()
        if isinstance(expected, bytes):
            return 0, None, self.telnet_client.read_until(expected, timeout=timeout)
        if isinstance(expected, re.Pattern):
            index, matches, data = self.telnet_client.expect([expected], timeout=timeout)
            return index, matches, data
        raise NotImplementedError()

    def write_expect(
            self,
            data: Union[str, bytes],
            expected: Union[str, bytes, re.Pattern] = None,
            timeout: float = 1):
        self.write_cmd(data)

        if isinstance(expected, re.Pattern):
            index, matches, output = self.read_expect(expected, timeout=timeout)
            if index == -1:
                raise Exception(f"Unexpected response from command '{data}'. Expected '{expected}' but received '{output}' after {timeout}s")
        else:
            index, matches, output = self.read_expect(expected, timeout=timeout).decode(errors="ignore")
            if expected:
                index_of_expected = output.find(expected)
                if not index_of_expected >= 0:
                    raise Exception(f"Unexpected response from command '{data}'. Expected '{expected}' but received '{output}' after {timeout}s")
                else:
                    output = output[: index_of_expected + len(expected)]
        return output
