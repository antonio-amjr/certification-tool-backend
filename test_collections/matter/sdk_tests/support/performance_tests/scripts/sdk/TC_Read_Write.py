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
import random
import string
import sys

import chip.clusters as Clusters

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../../")
    ),
)

from chip.testing.decorators import async_test_body
from chip.testing.runner import TestStep

from .library.base_test_classes.matter_qa_base_test_class import (
    MatterQABaseTestCaseClass,
)
from .library.base_test_classes.test_results_record import TestResultEnums
from .library.helper_libs.augmented_matter_test_base import run_augmented_matter_tests
from .library.helper_libs.exceptions import IterationError

log = logging.getLogger("base_tc")


class TC_Read_Write(MatterQABaseTestCaseClass):
    def __init__(self, *args):
        # Todo move this into some meta data
        self.test_suite_name = "StressTestSuite"
        self.tc_name = "Read_Write_SCRIPT"
        self.tc_id = "stress_1_4"
        self.dut_pair_status = False
        self.clusters = Clusters.Objects.BasicInformation
        super().__init__(*args)

    def pics_TC_read_write(self) -> list[str]:
        return ["STRESS.S"]

    def steps_TC_read_write(self) -> list[TestStep]:
        steps = [
            TestStep(
                1,
                "Device Factory Reset completed and Commission Ready",
                is_commissioning=True,
            )
        ]
        return steps

    def desc_TC_read_write(self) -> str:
        return "#.#.#. [TC-Read-Write] Stress Test"

    async def check_write_status(self, nodelabel_write_value):
        # This function is used to check the write command is executed successfully
        nodelabel_read_value = await self.read_single_attribute_check_success(
            cluster=self.clusters,
            attribute=Clusters.BasicInformation.Attributes.NodeLabel,
            endpoint=0,
        )
        if nodelabel_read_value == nodelabel_write_value:
            self.update_iteration_result(
                iteration_result=TestResultEnums.TEST_RESULT_PASS
            )
        else:
            log.info(
                "The iteration will be failed as there is no change in cluster state after write operation"
            )
            raise IterationError(
                "The Write attribute value is not match with the read value"
            )

    async def verify_read_write(self):
        # For checking the current Value of Node-label Attributes
        nodelabel_read_value = await self.read_single_attribute_check_success(
            cluster=self.clusters,
            attribute=Clusters.BasicInformation.Attributes.NodeLabel,
            endpoint=0,
        )

        log.info(f"The current value of the node label is {nodelabel_read_value}")
        random_string_length = 10
        nodelabel_write_value = "".join(
            random.choice(string.ascii_letters) for _ in range(random_string_length)
        )
        await self.default_controller.WriteAttribute(
            self.dut_node_id,
            [
                (
                    0,
                    Clusters.BasicInformation.Attributes.NodeLabel(
                        nodelabel_write_value
                    ),
                )
            ],
        )
        await self.check_write_status(nodelabel_write_value=nodelabel_write_value)

    @async_test_body
    async def test_TC_read_write(self):
        self.dut.factory_reset_dut()  # performing factory reset on DUT
        self.step(1)
        await self.perform_initial_commission_with_dut()

        @MatterQABaseTestCaseClass.iterate_tc(
            iterations=self.test_config.general_configs.number_of_iterations
        )
        async def tc_read_write(*args, **kwargs):
            time_before_read_write_cmd = datetime.datetime.now()
            try:
                log.info("starting Read-Write operation")
                await self.verify_read_write()
                time_after_read_write_cmd = datetime.datetime.now()
                read_write_api_duration = (
                    time_after_read_write_cmd - time_before_read_write_cmd
                ).total_seconds()
                self.analytics_dict.update(
                    {"read_write_api_duration": read_write_api_duration}
                )
                await self.fetch_analytics_from_dut()
                self.dut.reboot_dut()
                log.info("dut rebooted")
                self.default_controller.ExpireSessions(self.dut_node_id)
                self.iteration_test_result = TestResultEnums.TEST_RESULT_PASS
            except Exception as e:
                self.update_iteration_result(
                    iteration_result=TestResultEnums.TEST_RESULT_FAIL, execption=e
                )

        await tc_read_write(self)


if __name__ == "__main__":
    run_augmented_matter_tests(test_class=TC_Read_Write)

if __name__ == "__main__":
    run_augmented_matter_tests(test_class=TC_Read_Write)
