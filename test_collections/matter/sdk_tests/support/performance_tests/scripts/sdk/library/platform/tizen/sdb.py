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
import subprocess
import re

from .connector import TizenConnector, TizenApplicationStatus

log = logging.getLogger(__name__)


def create_connector(dut_config):
    return SDBConnector(dut_config)

class SDBConnector(TizenConnector):
    def __init__(self, dut_config) -> None:
        self.dut_config = dut_config
        self.sdb_args = []

        if hasattr(self.dut_config.connector.sdb, 'serial_no'):
            self.sdb_args.append(f"--serial '{self.dut_config.connector.sdb.serial_no}'")

        if hasattr(self.dut_config.connector.sdb, 'wait_for_device'):
            self.wait_for_device = getattr(self.dut_config.connector.sdb, 'wait_for_device')
        else:
            self.wait_for_device = False


    def open(self) -> None:
        log.debug("Opening connection")
        subprocess.run('sdb start-server', shell=True, check=True)
        if self.wait_for_device:
            subprocess.run(f"sdb {' '.join(self.sdb_args)} wait-for-device", shell=True, check=True)


    def close(self) -> None:
        log.debug("Closing connection")
        subprocess.run('sdb kill-server', shell=True, check=True)


    def run(self, command: str, **kwargs):
        command = f"sdb {' '.join(self.sdb_args)} shell {command}"
        log.debug(f"Running command '{command}' kwargs {kwargs}")
        # Always capture output just in case
        res = subprocess.run(command, shell=True, check=True, capture_output=True, encoding='utf-8', **kwargs)
        log.debug(f"Command result: {res}")
        log.debug(f"Command stdout: {res.stdout}")
        log.debug(f"Command stderr: {res.stderr}")
        return res


    def sudo(self, command, **kwargs):
        subprocess.run(f"sdb {' '.join(self.sdb_args)} root on", shell=True, check=True)
        res = self.run(command, **kwargs)
        subprocess.run(f"sdb {' '.join(self.sdb_args)} root off", shell=True, check=True)
        return res


    def app_status(self, app_package_id: str) -> TizenApplicationStatus:
        log.debug(f"Checking status for app '{app_package_id}'")
        res = self.run(f"'if app_launcher -S {app_package_id}; then "
                       "echo RUNNING; else echo STOPPED; fi'")

        status = TizenApplicationStatus()
        if 'RUNNING' in res.stdout:
            status.running = True
            m = re.search(rf'{app_package_id}\s+\((?P<pid>\d+)\)', res.stdout)
            if m:
                status.pid = m.group('pid')
        elif 'STOPPED' in res.stdout:
            status.running = False
        else:
            log.error(f'Unexpected command result: {res}')

        return status


    def stop_app(self, app_package_id: str) -> None:
        log.debug(f"Stopping application '{app_package_id}'")
        self.run(f"app_launcher -k '{app_package_id}'")
