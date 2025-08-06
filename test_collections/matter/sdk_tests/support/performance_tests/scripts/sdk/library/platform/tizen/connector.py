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
import importlib

from abc import ABC, abstractmethod
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class TizenApplicationStatus():
    """
    Object representing the runtime status of an application on a Tizen device.
    """
    running: bool = False  # True if the application is currently running on the device.
    pid: int = -1          # Process ID of the application, or -1 if it is not running.


class TizenConnector(ABC):
    @abstractmethod
    def __init__(self):
        pass


    @abstractmethod
    def open(self) -> None:
        pass


    @abstractmethod
    def close(self) -> None:
        pass


    @abstractmethod
    def run(self, command: str, **kwargs):
        """
        Will throw an exception if the command fails (ie. returns a non-zero exit code).
        """
        pass


    @abstractmethod
    def sudo(self, command, **kwargs):
        pass


    @abstractmethod
    def app_status(self, app_package_id: str) -> TizenApplicationStatus:
        pass


    @abstractmethod
    def stop_app(self, app_package_id: str) -> None:
        pass


def create_connector(dut_config) -> TizenConnector:
    connector_config = dut_config.connector
    if hasattr(connector_config, 'module'):
        log.info(f"Creating Tizen connector module '{connector_config.module}'")
        module = importlib.import_module(connector_config.module)
        return module.create_connector(dut_config)

    raise RuntimeError('Tizen connector module not specified')
