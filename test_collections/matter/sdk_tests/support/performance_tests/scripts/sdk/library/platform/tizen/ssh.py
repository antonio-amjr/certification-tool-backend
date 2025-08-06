#
#
#  Copyright (c) 2025 Project CHIP Authors
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

from fabric import Config, Connection

from .connector import TizenConnector, TizenApplicationStatus

log = logging.getLogger(__name__)


def create_connector(dut_config):
    """
    Connector object factory.
    """
    return SSHConnector(dut_config)


class SSHConnector(TizenConnector):
    """
    TizenConnector implementation using the fabric Connection object for SSH.
    """
    def __init__(self, dut_config):
        self.dut_config = dut_config
        ssh_config = dut_config.connector.ssh

        self.ssh_session = Connection(
            host = ssh_config.hostname,
            user = ssh_config.username,
            config = Config(overrides={'sudo': { 'password': ssh_config.sudo_password }}),
            connect_kwargs = { 'password': ssh_config.password }
        )


    def open(self) -> None:
        log.debug("Opening connection")
        self.ssh_session.open()


    def close(self) -> None:
        log.debug("Closing connection")
        self.ssh_session.close()


    def run(self, command, **kwargs):
        log.debug(f"Running command '{command}'")
        res = self.ssh_session.run(command, **kwargs)
        log.debug(f"Command result: {res}")
        return res


    def sudo(self, command, **kwargs):
        log.debug(f"Running command '{command}' with sudo")
        res = self.ssh_session.sudo(command, **kwargs)
        log.debug(f"Command result: {res}")
        return res


    def app_status(self, app_package_id: str) -> TizenApplicationStatus:
        log.info(f"Checking status for app '{app_package_id}'")
        command = f"app_launcher -S '{app_package_id}'"
        res = self.run(command, warn=True)
        status = TizenApplicationStatus(running=res.ok)

        if status.running:
            m = re.search(rf'{app_package_id} \((?P<pid>\d+)\)', res.stdout)
            if m:
                status.pid = m.group('pid')

        return status


    def stop_app(self, app_package_id: str) -> None:
        """
        Stop a running Tizen application.
        """
        log.debug(f"Stopping application '{app_package_id}'")
        self.run(f"app_launcher -k {app_package_id}")
