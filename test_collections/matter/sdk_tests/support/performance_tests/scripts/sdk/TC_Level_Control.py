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
from mobly import asserts

from .library.base_test_classes.matter_qa_base_test_class import (
    MatterQABaseTestCaseClass,
)
from .library.base_test_classes.test_results_record import TestResultEnums
from .library.helper_libs.augmented_matter_test_base import run_augmented_matter_tests
from .library.helper_libs.exceptions import IterationError

log = logging.getLogger("base_tc")


class TC_LEVEL_CONTROL(MatterQABaseTestCaseClass):
    def __init__(self, *args):
        # Todo move this into some meta data
        self.test_suite_name = "StressTestSuite"
        self.tc_name = "LEVEL_CONTROL_SCRIPT"
        self.tc_id = "stress_1_5"
        self.dut_pair_status = False
        super().__init__(*args)

    def pics_TC_LEVEL_CONTROL(self) -> list[str]:
        return ["STRESS.S"]

    def steps_TC_LEVEL_CONTROL(self) -> list[TestStep]:
        steps = [
            TestStep(
                1,
                "Device Factory Reset completed and Commission Ready",
                is_commissioning=True,
            )
        ]
        return steps

    def desc_TC_LEVEL_CONTROL(self) -> str:
        return "#.#.#. [TC-LEVEL-CONTROL] Stress Test "

    async def read_minimum_and_maximum_level_attribute(self):
        """
        Reads the minimum and maximum level values from the LevelControl cluster
        on endpoint 1 and stores them in instance variables.
        """
        try:
            # Reference to the LevelControl cluster
            self.level_control_cluster = Clusters.Objects.LevelControl

            # Read the minimum level supported by the device (e.g., lowest brightness)
            self.minimum_level = await self.read_single_attribute_check_success(
                cluster=self.level_control_cluster,
                attribute=Clusters.LevelControl.Attributes.MinLevel,
                endpoint=self.endpoint,
            )
            log.info(f"minimum_level attribute value is {self.minimum_level}")

            # Read the maximum level supported by the device (e.g., highest brightness)
            self.maximum_level = await self.read_single_attribute_check_success(
                cluster=self.level_control_cluster,
                attribute=Clusters.LevelControl.Attributes.MaxLevel,
                endpoint=self.endpoint,
            )
            log.info(f"maximum_level attribute value is {self.maximum_level}")

            # Adjust the maximum level by decrementing it to ensure we remain within the spec limits
            self.maximum_level = self.maximum_level - 1
        except Exception as e:
            asserts.fail(
                f"Failed to read the minimum_and_maximum_level_value from the dut: {e}"
            )

    def generate_new_level(self, current_level: int) -> int:
        """
        Generate a new level within the allowed range that is different from the current level.
        """
        new_level = current_level + 1
        # If the randomly generated level matches the current level, adjust it to force a change
        if new_level > self.maximum_level:
            new_level = self.minimum_level
        return new_level

    def validate_level_change(self, after_move_command_value, current_cluster_status):
        # This function is used to check the write command is executed successfully
        if after_move_command_value != current_cluster_status:
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

    async def send_and_validate_move_to_level_operation(self):
        try:
            # For checking the current level value
            current_level_value = await self.read_single_attribute_check_success(
                cluster=self.level_control_cluster,
                attribute=Clusters.LevelControl.Attributes.CurrentLevel,
                endpoint=self.endpoint,
            )
            log.info(f"CurrentLevel is {current_level_value}")

            # Ensure the new level is different from the current one
            new_level = self.generate_new_level(current_level_value)
            log.info(f"Sending MoveToLevel command with level: {new_level}")

            move_to_level_cmd = Clusters.LevelControl.Commands.MoveToLevel(
                level=new_level, transitionTime=0, optionsMask=1, optionsOverride=1
            )
            await self.default_controller.SendCommand(
                nodeid=self.dut_node_id,
                endpoint=self.endpoint,
                payload=move_to_level_cmd,
            )
            self.delay_between_stress_test_operations()
            after_move_command_value = await self.read_single_attribute_check_success(
                cluster=self.level_control_cluster,
                attribute=Clusters.LevelControl.Attributes.CurrentLevel,
                endpoint=self.endpoint,
            )

            self.validate_level_change(after_move_command_value, current_level_value)
        except Exception as e:
            log.error(e, exc_info=True)
            self.update_iteration_result(
                iteration_result=TestResultEnums.TEST_RESULT_FAIL, execption=e
            )

    @async_test_body
    async def test_TC_LEVEL_CONTROL(self):
        self.dut.factory_reset_dut()  # performing factory reset on DUT
        self.step(1)
        await self.perform_initial_commission_with_dut()
        self.endpoint = self.user_params.get("endpoint", 1)
        await self.read_minimum_and_maximum_level_attribute()

        @MatterQABaseTestCaseClass.iterate_tc(
            iterations=self.test_config.general_configs.number_of_iterations
        )
        async def TC_LEVEL_CONTROL(*args, **kwargs):
            try:
                log.info("starting Move-to-level operation")
                await self.send_and_validate_move_to_level_operation()
                await self.fetch_analytics_from_dut()
            except Exception as e:
                self.update_iteration_result(
                    iteration_result=TestResultEnums.TEST_RESULT_FAIL, execption=e
                )

        await TC_LEVEL_CONTROL(self)


if __name__ == "__main__":
    run_augmented_matter_tests(test_class=TC_LEVEL_CONTROL)
    run_augmented_matter_tests(test_class=TC_LEVEL_CONTROL)
