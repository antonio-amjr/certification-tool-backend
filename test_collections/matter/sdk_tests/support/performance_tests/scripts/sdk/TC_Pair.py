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
import sys

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


class TC_Pair(MatterQABaseTestCaseClass):
    def __init__(self, *args):
        # Todo move this into some meta data
        self.test_suite_name = "StressTestSuite"
        self.tc_name = "Pair_Unpair"
        self.tc_id = "stress_1_1"
        super().__init__(*args)

    def pics_TC_pair_unpair(self) -> list[str]:
        return ["STRESS.S"]

    def steps_TC_pair_unpair(self) -> list[TestStep]:
        steps = [
            TestStep(
                1,
                "Device Factory Reset completed and Commission Ready",
                is_commissioning=True,
            )
        ]
        return steps

    def desc_TC_pair_unpair(self) -> str:
        return "#.#.#. [TC-Pair_Unpair] Stress Test "

    @async_test_body
    async def test_TC_pair_unpair(self):
        self.perform_initial_factory_reset()  # Perform initial factory reset as per the configuration
        self.step(1)

        @MatterQABaseTestCaseClass.iterate_tc(
            iterations=self.test_config.general_configs.number_of_iterations
        )
        async def tc_pair_unpair(*args, **kwargs):
            if self.do_factory_reset_every_iteration():
                await self.perform_factory_reset_dut()  # perform factory reset on DUT before starting the pairing operation
            time_before_starting_pairing = datetime.datetime.now()
            try:
                pairing_status_dut = (
                    await self.pair_dut()
                )  # pairing operation with DUT begins.
                if pairing_status_dut:
                    log.info(
                        "Device has been Commissioned starting pair-unpair operation"
                    )
                    time_after_pairing_completed = datetime.datetime.now()
                    pairing_duration = (
                        time_after_pairing_completed - time_before_starting_pairing
                    ).total_seconds()
                    self.analytics_dict.update({"pairing_duration": pairing_duration})
                    await self.fetch_analytics_from_dut()
                    # Delay to allow the system to stabilize after pairing
                    self.delay_between_stress_test_operations()
                    if not self.use_test_event_trigger_factory_reset:
                        await self.unpair_dut()
                    self.update_iteration_result(
                        iteration_result=TestResultEnums.TEST_RESULT_PASS
                    )
                else:
                    raise IterationError(pairing_status_dut.exception)
            except Exception as e:
                self.update_iteration_result(
                    iteration_result=TestResultEnums.TEST_RESULT_FAIL, execption=e
                )

        await tc_pair_unpair(self)


if __name__ == "__main__":
    run_augmented_matter_tests(test_class=TC_Pair)


if __name__ == "__main__":
    run_augmented_matter_tests(test_class=TC_Pair)
