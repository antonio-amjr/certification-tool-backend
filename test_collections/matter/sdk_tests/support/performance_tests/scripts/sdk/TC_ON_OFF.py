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
import os
import sys

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../../")
    ),
)

import chip.clusters as Clusters
from chip.testing.decorators import async_test_body
from chip.testing.runner import TestStep

from .library.base_test_classes.matter_qa_base_test_class import (
    MatterQABaseTestCaseClass,
)
from .library.base_test_classes.test_results_record import TestResultEnums
from .library.helper_libs.augmented_matter_test_base import run_augmented_matter_tests
from .library.helper_libs.exceptions import IterationError

log = logging.getLogger("base_tc")


class TC_ON_OFF(MatterQABaseTestCaseClass):
    def __init__(self, *args):
        # Todo move this into some meta data
        self.test_suite_name = "StressTestSuite"
        self.tc_name = "ON_OFF_SCRIPT"
        self.tc_id = "stress_1_3"
        self.dut_pair_status = False
        super().__init__(*args)

    def pics_TC_on_off(self) -> list[str]:
        return ["STRESS.S"]

    def steps_TC_on_off(self) -> list[TestStep]:
        steps = [
            TestStep(
                1,
                "Device Factory Reset completed and Commission Ready",
                is_commissioning=True,
            )
        ]
        return steps

    def desc_TC_on_off(self) -> str:
        return "#.#.#. [TC-ON-OFF] Stress Test "

    def check_cluster_status(
        self, after_operation_cluster_status, current_cluster_status
    ):
        # This function is used to check the write command is executed successfully
        if after_operation_cluster_status != current_cluster_status:
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

    async def verify_switch_on_off_cluster(self):
        try:
            clusters = Clusters.Objects.OnOff
            # For checking the current State of On-OFF cluster
            current_cluster_status = await self.read_single_attribute_check_success(
                cluster=clusters, attribute=Clusters.OnOff.Attributes.OnOff, endpoint=1
            )
            # if current_cluster_status is True then cluster is in ON state else it is OFF
            log.info(
                f"The ON-OFF cluster's current condition is {'ON' if current_cluster_status is True else 'OFF'}"
            )

            # This condition will write the opposite value of read
            await self.default_controller.SendCommand(
                nodeid=self.dut_node_id,
                endpoint=1,
                payload=Clusters.OnOff.Commands.Toggle(),
            )
            after_operation_cluster_status = (
                await self.read_single_attribute_check_success(
                    cluster=clusters,
                    attribute=Clusters.OnOff.Attributes.OnOff,
                    endpoint=1,
                )
            )

            self.check_cluster_status(
                after_operation_cluster_status, current_cluster_status
            )
        except Exception as e:
            log.error(e, exc_info=True)
            self.update_iteration_result(
                iteration_result=TestResultEnums.TEST_RESULT_FAIL, execption=e
            )

    @async_test_body
    async def test_TC_on_off(self):
        self.dut.factory_reset_dut()  # performing factory reset on DUT
        self.step(1)
        await self.perform_initial_commission_with_dut()

        @MatterQABaseTestCaseClass.iterate_tc(
            iterations=self.test_config.general_configs.number_of_iterations
        )
        async def tc_on_off(*args, **kwargs):
            try:
                log.info("starting ON - OFF  operation")
                await self.verify_switch_on_off_cluster()
                await self.fetch_analytics_from_dut()
            except Exception as e:
                self.update_iteration_result(
                    iteration_result=TestResultEnums.TEST_RESULT_FAIL, execption=e
                )

        await tc_on_off(self)


if __name__ == "__main__":
    run_augmented_matter_tests(test_class=TC_ON_OFF)

if __name__ == "__main__":
    run_augmented_matter_tests(test_class=TC_ON_OFF)
