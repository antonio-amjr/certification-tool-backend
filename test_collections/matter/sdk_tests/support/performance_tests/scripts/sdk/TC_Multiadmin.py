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
import queue
import sys
import time
import typing

import chip.clusters as Clusters

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../../")
    ),
)

from chip.commissioning import CommissionFailure
from chip.testing.decorators import async_test_body
from chip.testing.runner import TestStep

from .library.base_test_classes.matter_qa_base_test_class import (
    MatterQABaseTestCaseClass,
)
from .library.base_test_classes.test_results_record import TestResultEnums
from .library.helper_libs.augmented_matter_test_base import (
    AttributeChangeAccumulator,
    run_augmented_matter_tests,
)
from .library.helper_libs.exceptions import IterationError, TestCaseExit

log = logging.getLogger("base_tc")


class TC_Multiadmin(MatterQABaseTestCaseClass):
    def __init__(self, *args):
        # Todo move this into some meta data
        self.test_suite_name = "StressTestSuite"
        self.tc_name = "Multi_Admin"
        self.tc_id = "stress_1_2"
        super().__init__(*args)
        self.output_queue = queue.Queue()
        try:
            self.open_commissioning_window_timeout_seconds = (
                self.test_config.test_case_config.TC_Multiadmin.open_commissioning_window_timeout
            )
        except Exception as e:
            log.error(
                f"Failed to read commissioning_window_timeout from config using default value ",
                exc_info=True,
            )
            self.open_commissioning_window_timeout_seconds = 300

    def pics_TC_multiadmin(self) -> typing.List[str]:
        return ["STRESS.S"]

    def steps_TC_multiadmin(self) -> typing.List[TestStep]:
        steps = [
            TestStep(
                1,
                "Device Factory Reset completed and Commission Ready",
                is_commissioning=True,
            )
        ]
        return steps

    def desc_TC_multiadmin(self) -> str:
        return "#.#.#. [TC-Multiadmin] Stress Test "

    def create_unique_controller_id(self, fabric):
        # To create a unique_controller_id value for each controller
        return fabric + 1  # Increment the fabric value by 1

    def create_unique_node_id(self, fabric):
        # To create a unique node_id for each controller
        return (
            self.dut_node_id
            + fabric
            + (
                (self.test_config.current_iteration - 1)
                * self.max_fabric_supported_by_dut
            )
        )

    async def create_list_of_controller_object(self):
        self.max_fabric_supported_by_dut = await self.read_single_attribute(
            self.default_controller,
            self.dut_node_id,
            0,
            Clusters.OperationalCredentials.Attributes.SupportedFabrics,
        )
        list_of_paired_controllers = []
        for fabric in range(1, self.max_fabric_supported_by_dut):
            unique_controller_id = self.create_unique_controller_id(fabric)
            controller_object = self.build_controller_object(unique_controller_id)
            unique_node_id = self.create_unique_node_id(fabric)
            list_of_paired_controllers.append((controller_object, unique_node_id))
        return list_of_paired_controllers

    async def read_subscription_interval_duration(self):
        try:
            self.max_report_interval_seconds = int(
                await self.read_single_attribute_check_success(
                    dev_ctrl=self.default_controller,
                    node_id=self.dut_node_id,
                    endpoint=0,
                    attribute=Clusters.IcdManagement.Attributes.IdleModeDuration,
                    cluster=Clusters.IcdManagement,
                    assert_on_error=False,
                )
            )
            self.min_report_interval_seconds = 0
        except Exception as e:
            log.error(
                f"Failed to read_subscription_interval_duration with error{e} hence using default values",
                exc_info=True,
            )
            self.max_report_interval_seconds = 600
            self.min_report_interval_seconds = 0

    def check_subscription_report(self):
        # To check the subcription report data from each of the controller
        list_of_controller_with_updated_subcription_report = []
        timeout_delay_seconds = self.max_report_interval_seconds
        start_time = time.time()
        elapsed_seconds = 0
        # time_remaining variable is used to break the below loop
        time_remaining = timeout_delay_seconds

        while time_remaining > 0:
            try:
                subcription_report = self.output_queue.get(
                    block=True, timeout=time_remaining
                )
                controller_name = subcription_report.name
                endpoint = subcription_report.endpoint
                attribute = subcription_report.attribute
                subcription_value = subcription_report.value

                if (
                    endpoint == 0
                    and attribute == Clusters.BasicInformation.Attributes.NodeLabel
                    and subcription_value == "After Subscriptions"
                ):
                    if (
                        not controller_name
                        in list_of_controller_with_updated_subcription_report
                    ):
                        log.info(
                            "Got expected attribute change for client %s"
                            % controller_name
                        )
                        list_of_controller_with_updated_subcription_report.append(
                            controller_name
                        )

                if len(list_of_controller_with_updated_subcription_report) == len(
                    self.list_of_controller_objects
                ):
                    log.info("All fabrics are reported, done waiting.")
                    break
            except queue.Empty:
                # No error, we update timeouts and keep going
                pass

            elapsed_seconds = time.time() - start_time
            time_remaining = timeout_delay_seconds - elapsed_seconds

    async def cleaning_up_the_paired_controller(
        self, list_of_paired_controllers, list_of_subscriptions
    ):
        try:
            unpairing_duration_for_each_controller = {}
            for subscription in list_of_subscriptions:
                subscription.Shutdown()
            for controller_object, nodeid in list_of_paired_controllers:
                time_before_starting_unpair = datetime.datetime.now()
                log.info(f"Unpairing the {controller_object.name} from the DUT")
                await self.unpair_dut(controller_object, nodeid)
                time_after_unpairing_completed = datetime.datetime.now()
                unpairing_duration = (
                    time_after_unpairing_completed - time_before_starting_unpair
                ).total_seconds()
                unpairing_duration_for_each_controller.update(
                    {controller_object.name: unpairing_duration}
                )
            # Condition to set the iteration result
            if len(list_of_paired_controllers) == self.max_fabric_supported_by_dut - 1:
                self.update_iteration_result(
                    iteration_result=TestResultEnums.TEST_RESULT_PASS
                )
            total_unpairing_duration_for_each_controller = sum(
                unpairing_duration_for_each_controller.values()
            )
            self.analytics_dict.update(
                {
                    "total_unpairing_duration": total_unpairing_duration_for_each_controller
                }
            )
            if len(unpairing_duration_for_each_controller) == 0:
                raise IterationError(
                    "Failed to calculate average unpairing duration for_each_controller as 0 "
                    "number of controllers was un-paired"
                )
            average_unpairing_duration_for_each_controller = (
                total_unpairing_duration_for_each_controller
                / len(unpairing_duration_for_each_controller)
            )
            self.analytics_dict.update(
                {
                    "average_unpairing_duration": average_unpairing_duration_for_each_controller
                }
            )
            log.info(
                f"Average unpairing duration for each controller in iteration-{self.test_config.current_iteration} \
                        is {average_unpairing_duration_for_each_controller}"
            )
            log.info(
                f"unpairing duration for each controller in iteration-{self.test_config.current_iteration} \
                        is {unpairing_duration_for_each_controller}"
            )

        except Exception as e:
            # When the unpairing of 1 controller is failed all the upcoming iteration will be failed
            # Hence terminating the testcase using TestCaseExit Exception
            self.mark_iteration_failure_sync_mobly_and_summary_data(str(e))
            log.error("Failed to unpair the controller{}".format(e), exc_info=True)
            raise TestCaseExit(str(e))

    @async_test_body
    async def test_TC_multiadmin(self):
        self.dut.factory_reset_dut()  # performing factory reset on DUT
        self.step(1)
        await self.perform_initial_commission_with_dut()
        self.list_of_controller_objects = await self.create_list_of_controller_object()
        await self.read_subscription_interval_duration()

        @MatterQABaseTestCaseClass.iterate_tc(
            iterations=self.test_config.general_configs.number_of_iterations
        )
        async def tc_multi_admin(*args, **kwargs):
            # List contains the controller object
            list_of_paired_controllers = []
            list_of_subscriptions = []
            pairing_duration_for_each_controller = {}
            try:
                # Writing the value="Before Subscriptions" before the subscription
                await self.default_controller.WriteAttribute(
                    self.dut_node_id,
                    [
                        (
                            0,
                            Clusters.BasicInformation.Attributes.NodeLabel(
                                value="Before Subscriptions"
                            ),
                        )
                    ],
                )

                for controller, nodeid in self.list_of_controller_objects:
                    log.info(
                        f"Started the commissioning process for the {controller.name}"
                    )
                    time_before_starting_pairing = datetime.datetime.now()
                    log.info(
                        f"Opening the commissioning window for the {controller.name}"
                    )
                    open_commissioning_window_parameters = await self.openCommissioningWindow(
                        dev_ctrl=self.default_controller,
                        node_id=self.dut_node_id,
                        commissioning_window_timeout=self.open_commissioning_window_timeout_seconds,
                    )
                    await self.pair_controller_with_dut(
                        controller, nodeid, open_commissioning_window_parameters
                    )
                    time_after_pairing_completed = datetime.datetime.now()
                    pairing_duration = (
                        time_after_pairing_completed - time_before_starting_pairing
                    ).total_seconds()
                    log.info(f"{controller.name} is commissioned")
                    pairing_duration_for_each_controller.update(
                        {controller.name: pairing_duration}
                    )
                    log.info(
                        f"Paring duration of the {controller.name} is {pairing_duration}"
                    )
                    list_of_paired_controllers.append((controller, nodeid))
                    log.info(
                        f"Subscribing to the node-label attribute from the {controller.name}"
                    )
                    subscription = await controller.ReadAttribute(
                        nodeid=nodeid,
                        attributes=[
                            (0, Clusters.BasicInformation.Attributes.NodeLabel)
                        ],
                        reportInterval=(
                            self.min_report_interval_seconds,
                            self.max_report_interval_seconds,
                        ),
                        keepSubscriptions=False,
                    )
                    list_of_subscriptions.append(subscription)
                    subscription_report_callback = AttributeChangeAccumulator(
                        name=controller.name,
                        expected_attribute=Clusters.BasicInformation.Attributes.NodeLabel,
                        output=self.output_queue,
                    )
                    subscription.SetAttributeUpdateCallback(
                        subscription_report_callback
                    )
                    # we are adding delay so that DUT is in a stable state before unpairing this can be controlled from configFile
                    self.delay_between_stress_test_operations()

                total_pairing_duration_for_each_controller = sum(
                    pairing_duration_for_each_controller.values()
                )
                self.analytics_dict.update(
                    {
                        "total_pairing_duration": total_pairing_duration_for_each_controller
                    }
                )
                average_pairing_duration_for_each_controller = (
                    total_pairing_duration_for_each_controller
                    / len(pairing_duration_for_each_controller)
                )
                self.analytics_dict.update(
                    {
                        "average_pairing_duration": average_pairing_duration_for_each_controller
                    }
                )
                log.info(
                    f"Average pairing duration for each controller in iteration-{self.test_config.current_iteration} \
                         is {average_pairing_duration_for_each_controller}"
                )
                log.info(
                    f"pairing duration for each controller in iteration-{self.test_config.current_iteration} \
                         is {pairing_duration_for_each_controller}"
                )
                time_before_start_reading_subscription = datetime.datetime.now()
                log.info(
                    f"Writing the value='After Subscriptions' to validate the subscription report"
                )
                await self.default_controller.WriteAttribute(
                    self.dut_node_id,
                    [
                        (
                            0,
                            Clusters.BasicInformation.Attributes.NodeLabel(
                                value="After Subscriptions"
                            ),
                        )
                    ],
                )
                self.check_subscription_report()
                time_after_reading_subscription = datetime.datetime.now()
                subscription_duration = (
                    time_after_reading_subscription
                    - time_before_start_reading_subscription
                ).total_seconds()
                self.analytics_dict.update(
                    {"subscription_duration": subscription_duration}
                )
                log.info(
                    f"subscription_duration for all controller in iteration-{self.test_config.current_iteration} \
                         is {subscription_duration}"
                )
            except CommissionFailure as e:
                log.error(str(e), exc_info=True)
                self.update_iteration_result(
                    iteration_result=TestResultEnums.TEST_RESULT_FAIL, execption=e
                )
                await self.close_commissioning_window(
                    self.open_commissioning_window_timeout_seconds
                )
            except Exception as e:
                log.error(str(e), exc_info=True)
                self.update_iteration_result(
                    iteration_result=TestResultEnums.TEST_RESULT_FAIL, execption=e
                )

            await self.cleaning_up_the_paired_controller(
                list_of_paired_controllers, list_of_subscriptions
            )
            await self.fetch_analytics_from_dut()

        await tc_multi_admin(self)


if __name__ == "__main__":
    run_augmented_matter_tests(test_class=TC_Multiadmin)
