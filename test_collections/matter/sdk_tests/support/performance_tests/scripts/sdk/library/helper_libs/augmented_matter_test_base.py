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
import argparse
import asyncio
import io
import json
import logging
import os
import pathlib
import queue
import random
import secrets
import sys
import time
import traceback
import typing
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import yaml
from chip import clusters as Clusters
from chip import ChipDeviceCtrl
from chip.ChipDeviceCtrl import CHIP_ERROR_TIMEOUT
from chip.clusters import ClusterObjects
from chip.clusters.Attribute import TypedAttributePath, SubscriptionTransaction
from chip.commissioning import CommissionFailure
from chip.exceptions import ChipStackError
from chip.interaction_model import InteractionModelError
from chip.testing.global_stash import stash_globally
from chip.testing.matter_testing import MatterBaseTest, parse_matter_test_args, MatterTestConfig, MatterStackState
from chip.testing.commissioning import commission_device, CommissioningInfo, CustomCommissioningParameters
from chip.testing.runner import InternalTestRunnerHooks, generate_mobly_test_config, TestRunnerHooks
from chip.tracing import TracingContext
from matter_qa.library.base_test_classes.enums.matterqa_base_enums import OperationalTimingEnums
from mobly import signals, asserts
from mobly.test_runner import TestRunner

log = logging.getLogger("base_tc")

DiscoveryFilterType = ChipDeviceCtrl.DiscoveryFilterType

def read_config_from_file(reliability_test_arg_fp) -> typing.Dict[str, bool]:
    try:

        test_config_dict = yaml.safe_load(reliability_test_arg_fp)
        return test_config_dict
    except Exception as e:
        log.error(e,exc_info=True)
        sys.exit(1)

def update_nested_key(reliability_tests_config, config_to_overwrite):
    for key, value in config_to_overwrite.items():
        if isinstance(value, dict):
            # If the key is not present, initialize as an empty dict
            if key not in reliability_tests_config:
                log.info(f"Key {key} not found, initializing as an empty dictionary.")
                reliability_tests_config[key] = {}
            update_nested_key(reliability_tests_config[key], value)
        else:
            # Directly assign the value
            reliability_tests_config[key] = value
    log.info("Updated reliability_tests_config:", reliability_tests_config)


def append_stress_test_args(matter_test_config):
    parser = argparse.ArgumentParser(description='Matter standalone Python test')
    reliability_tests_group = parser.add_argument_group(title="reliability test argument",
                                                        description="reliability test case global arguments set")
    reliability_tests_group.add_argument('--reliability-tests-arg', type=argparse.FileType('r', encoding='utf-8'),
                                         help="file path representing the configfile used by user to start the executing test")
    reliability_tests_group.add_argument('--overwrite-reliability-tests-args', type=str,
                                         help="JSON string to overwrite reliability test configuration")
    argv = sys.argv[1:]
    all_args = parser.parse_known_args(argv)[0]
    setattr(matter_test_config, "reliability_tests_config",
            {} if all_args.reliability_tests_arg is None else read_config_from_file(all_args.reliability_tests_arg))
    if all_args.overwrite_reliability_tests_args:
        config_to_overwrite = json.loads(all_args.overwrite_reliability_tests_args)
        log.info("Parsed JSON config_to_overwrite:", config_to_overwrite)
        update_nested_key(matter_test_config.reliability_tests_config, config_to_overwrite)


async def async_delay_between_stress_test_operations(test_config:MatterTestConfig, delay_between_operations=0.2):
    """

    this function can be used to delay between stress test operations. It will read from configFile the key
    'delay_between_stress_test_operations' and provide delay, if the key is missing then it will default to 5 seconds.
    for example the DUT may take 5 seconds after pairing operation to have settle down before unpairing is initiated
    this function can be used efficiently to be provided such relax time to the DUT.
    Returns:
        no data returned
    """
    if hasattr(test_config.general_configs, "delay_between_stress_test_operations"):
        delay_between_operations = test_config.general_configs.delay_between_stress_test_operations
    log.info(f"adding delay of {delay_between_operations} seconds between stress test operations")
    await asyncio.sleep(delay_between_operations)


class AugmentedMatterTestBase(MatterBaseTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)

    @staticmethod
    def _reset_commissioning_event(controller):
        if controller._commissioning_context.future is not None:
            controller._commissioning_context.future.done()
            controller._commissioning_context.future.set_result(None)

    async def pair_dut(self):
        try:
            setup_payloads = self.get_setup_payload_info()
            if len(setup_payloads) > 0:
                setup_payload = setup_payloads[0]
            else:
                raise Exception(
                    "setup_payload_info is empty, check the code for populating the test config of python controller")
            node_id = secrets.randbelow(2 ** 32)
            self.matter_test_config.dut_node_ids[0] = node_id
            commissioning_info: CommissioningInfo = CommissioningInfo(
                commissionee_ip_address_just_for_testing=self.matter_test_config.commissionee_ip_address_just_for_testing,
                commissioning_method=self.matter_test_config.commissioning_method,
                thread_operational_dataset=self.matter_test_config.thread_operational_dataset,
                wifi_passphrase=self.matter_test_config.wifi_passphrase,
                wifi_ssid=self.matter_test_config.wifi_ssid,
                tc_version_to_simulate=self.matter_test_config.tc_version_to_simulate,
                tc_user_response_to_simulate=self.matter_test_config.tc_user_response_to_simulate,
            )
            commission_device_result = await commission_device(dev_ctrl=self.default_controller, node_id=node_id,
                                                               info=setup_payload,
                                                               commissioning_info=commissioning_info
                                                               )
            self.default_controller.ResetCommissioningParameters()
            self._reset_commissioning_event(self.default_controller)
            return commission_device_result
        except Exception as e:
            raise CommissionFailure(e)

    async def unpair_dut(self, controller=None, node_id=None) -> bool:
        try:
            if controller is None and node_id is None:
                controller = self.default_controller
                node_id = self.dut_node_id

            await controller.UnpairDevice(node_id)
            controller.ExpireSessions(node_id)
            log.info("unpair_dut completed successfully")
            return True

        except Exception as e:
            log.error(e, exc_info=True)
            # we will directly raise the original exception directly to maintain the traceback
            raise

    async def close_commissioning_window(self, commissioning_window_timeout: int = 900):
        try:
            # Closing the Commissioning window using revoke commissioning command
            await self.default_controller.SendCommand(nodeid=self.dut_node_id, endpoint=0, payload=Clusters.AdministratorCommissioning.Commands.RevokeCommissioning(),
                                                      timedRequestTimeoutMs=6000)
        except Exception as e:
            log.info(f"RevokeCommissioning command is Failed {e} , hence waiting for commissioing window to close")
            # Waiting for the commissioning window to close
            time.sleep(commissioning_window_timeout)

    async def openCommissioningWindow(self, dev_ctrl: ChipDeviceCtrl, node_id: int, commissioning_window_timeout: int = 900) \
            -> CustomCommissioningParameters:
        rnd_discriminator = random.randint(0, 4095)
        try:
            commissioning_params = await dev_ctrl.OpenCommissioningWindow(nodeid=node_id, timeout=commissioning_window_timeout,
                                                                          iteration=1000, discriminator=rnd_discriminator,
                                                                          option=1)
            params = CustomCommissioningParameters(commissioning_params, rnd_discriminator)
            return params

        except InteractionModelError as e:
            asserts.fail(e.status, 'Failed to open commissioning window')

    async def pair_controller_with_dut(self, custom_controller_object: ChipDeviceCtrl, nodeid: int,
                                       open_commissioning_window_parameters: CustomCommissioningParameters):
        """
        Pairs a custom controller with the DUT using the provided commissioning parameters.

        Args:
            custom_controller_object: The controller to be paired with the DUT
            nodeid: The node ID to assign to the DUT
            open_commissioning_window_parameters: Commissioning parameters including setup PIN and discriminator

        Raises:
            CommissionFailure: If commissioning fails after retries

        Note:
            CommissionOnNetwork returns an int (effective node ID) on success and raises ChipStackError on failure.
        """
        try:
            log.info(f'Commissioning process with DUT has been initialized')

            # Extract commissioning parameters Setup_pincode and discriminator for the custom controller object
            setup_pincode = open_commissioning_window_parameters.commissioningParameters.setupPinCode
            discriminator = open_commissioning_window_parameters.randomDiscriminator

            # Reset the test commissioner to ensure a clean state
            custom_controller_object.ResetTestCommissioner()

            try:
                # Attempt to commission the device on the network using the provided parameters
                # CommissionOnNetwork returns an int (effective node ID) on success
                effective_node_id = await custom_controller_object.CommissionOnNetwork(
                    nodeId=nodeid,
                    setupPinCode=setup_pincode,
                    filterType=DiscoveryFilterType.LONG_DISCRIMINATOR,
                    filter=discriminator
                )

                log.info(f"Successfully commissioned device with effective node ID: {effective_node_id}")

            except ChipStackError as commissioning_error:
                # If commissioning fails with a timeout error, enter retrying loop
                # This gives the DUT more time to respond before giving up
                if commissioning_error.code == CHIP_ERROR_TIMEOUT:
                    log.warning("Commissioning timed out; entering retrying loop...")

                    # How often (1 second) to retry for commissioning completion
                    retry_interval_between_commissioning_attempts = OperationalTimingEnums.RETRY_INTERVAL.value
                    # Maximum total time (50 seconds) to keep retrying before giving up
                    max_waiting_time = OperationalTimingEnums.OVERALL_TIMEOUT.value
                    start_time = time.time()

                    commissioning_succeeded = False

                    # Check if commissioning has succeeded via the commissioning context future
                    while time.time() - start_time < max_waiting_time and not commissioning_succeeded:
                        await asyncio.sleep(retry_interval_between_commissioning_attempts)

                        # Check if commissioning has succeeded in the meantime
                        future = custom_controller_object._commissioning_context.future

                        if future is not None and future.done():
                            try:
                                future_result = future.result()
                                # If future returns successfully, commissioning completed
                                if future_result is not None:
                                    log.info(f"Commissioning completed via future with result: {future_result}")
                                    commissioning_succeeded = True
                                    break
                            except Exception as future_exception:
                                # If future completed with exception, commissioning failed
                                log.error(f"Commissioning failed via future: {future_exception}")
                                raise CommissionFailure(f"Failed to pair the controller: {future_exception}")

                    # If retrying completed but still no success, raise the original timeout error
                    if not commissioning_succeeded:
                        log.error(f"Commissioning timed out after {max_waiting_time} seconds")
                        raise CommissionFailure(f"Failed to pair the controller: {commissioning_error}")

                # If the error was not a timeout, re-raise immediately
                else:
                    log.error(
                        f"Failed to Commission the {custom_controller_object.name} with DUT: {commissioning_error}")
                    raise CommissionFailure(f"Failed to pair the controller: {commissioning_error}")

            # Reset any temporary commissioning parameters from controller
            custom_controller_object.ResetCommissioningParameters()
            self._reset_commissioning_event(custom_controller_object)

        except Exception as e:
            log.error(f"Unexpected error during commissioning: {e}", exc_info=True)
            raise CommissionFailure(f"Failed to pair the controller {e}")

    def build_controller_object(self, controller_id: int):
        # This function is used to build the controllers
        try:
            log.info(f'Controller node id for controller-{controller_id}')
            # This object is used to create a new empty list in CA Index
            th_certificate_authority = self.certificate_authority_manager.NewCertificateAuthority()
            th_fabric_admin = th_certificate_authority.NewFabricAdmin(vendorId=0xFFF1, fabricId= controller_id + 1)
            controller_object = th_fabric_admin.NewController(controller_id)
            controller_object.name = f"TH-{controller_id}"
            return controller_object
        # This exception will be caught if we are unable to build the controller
        except Exception as e:
            raise ValueError(f"Failed to build controller {e}")

    async def retrieve_diagnostic_logs_from_device(self, endpoint: int, test_config: MatterTestConfig,
                                                   full_diagnostic_log_path,
                                                   diagnostic_log_type: Clusters.DiagnosticLogs.Enums.IntentEnum = None,
                                                   bdx_transfer_timeout: int = 5,
                                                   max_retries: int = 3) -> None:
        """
        Retrieve diagnostic logs using BDX (preferred) or inline logContent.

        Args:
            endpoint (int): The device endpoint to target.
            full_diagnostic_log_path (str): Path to save retrieved logs.
            diagnostic_log_type (Optional[Clusters.DiagnosticLogs.Enums.IntentEnum]): The type of diagnostic log to retrieve.
            max_retries (int): Maximum number of retries for retrieving Diagnostic logs from DUT in case of failure.
            delay_between_operations (float): Delay (in seconds) between operations, to avoid stressing the DUT.
            bdx_transfer_timeout (int): Timeout duration (in seconds) to wait for BDX transfer to start.

        Returns:
            None.
        """
        diagnostic_log_fetch_attempt = 0  # Tracks the number of attempts to retry fetching diagnostic logs from the DUT

        while diagnostic_log_fetch_attempt < max_retries:
            diagnostic_log_fetch_attempt += 1
            log.info(f"[{diagnostic_log_type.name}] Attempt {diagnostic_log_fetch_attempt} of {max_retries}")
            dut_diag_logs_data = None  # Holds logs data once it's retrieved
            try:

                await async_delay_between_stress_test_operations(test_config)
                bdx_future: asyncio.Future = self.default_controller.TestOnlyPrepareToReceiveBdxData()
                diag_logs_filename = os.path.basename(full_diagnostic_log_path)

                # Construct the RetrieveLogsRequest command with BDX protocol and the transfer file designator
                command = Clusters.DiagnosticLogs.Commands.RetrieveLogsRequest(
                    intent=diagnostic_log_type,
                    requestedProtocol=Clusters.DiagnosticLogs.Enums.TransferProtocolEnum.kBdx,
                    transferFileDesignator=diag_logs_filename
                )
                # Send the RetrieveLogsRequest command asynchronously (but do not await it yet)
                command_send_future = asyncio.create_task(
                    self.default_controller.SendCommand(
                        nodeid=self.dut_node_id,
                        endpoint=endpoint if endpoint else 0,  # diagnostic logs cluster is supported only on endpoint 0
                        payload=command,
                        responseType=Clusters.DiagnosticLogs.Commands.RetrieveLogsResponse,
                    )
                )

                try:
                    log.info("Waiting for BDX transfer to start...")
                    # Wait for the BDX transfer to start (with a timeout to avoid hanging)
                    dut_bdx_transfer_session = await asyncio.wait_for(bdx_future, timeout=bdx_transfer_timeout)
                    log.info("BDX transfer initiated.")
                    # Accept and receive the log data via BDX
                    await dut_bdx_transfer_session.accept_and_receive_data()
                    dut_diag_logs_data = dut_bdx_transfer_session._data
                    # Close the BDX session if possible (cleanup)
                    if hasattr(dut_bdx_transfer_session, "close"):
                        await dut_bdx_transfer_session.close()
                        log.info("BDX transfer closed.")

                    # If the command_send_future is still running, cancel it as BDX transfer succeeded
                    if not command_send_future.done():
                        command_send_future.cancel()
                        log.info("Cancelled unused command future after BDX path.")

                except asyncio.TimeoutError:
                    # If BDX transfer does not start in time, fall back to waiting for inline log response
                    log.info("BDX not started — falling back to inline response.")
                    command_response = await command_send_future

                    # Check if logs are available inline in the response
                    if (command_response.status == Clusters.DiagnosticLogs.Enums.StatusEnum.kExhausted and
                            command_response.logContent):
                        dut_diag_logs_data = command_response.logContent
                    else:
                        # Neither BDX nor inline response provided logs; raise error to trigger retry or failure
                        raise RuntimeError(
                            f"No logs received for {diagnostic_log_type.name}. "
                            f"Status: {command_response.status}, Response: {command_response}"
                        )

                # Save the received logs to the specified file path, if any log data was retrieved
                with open(full_diagnostic_log_path, "wb") as f:
                    f.write(dut_diag_logs_data)
                    log.info(f"{diagnostic_log_type.name} logs written to {full_diagnostic_log_path}")
                return

            except ChipStackError as chip_err:
                log.warning(f"CHIP Error while retrieving {diagnostic_log_type.name}: {chip_err}")
                if "Timeout" in str(chip_err):
                    log.warning(f"{diagnostic_log_type.name} request timed out. Retrying...")
                    continue

            except asyncio.CancelledError:
                log.warning("Command send task was cancelled (likely due to BDX path)")
                continue

            except Exception as e:
                log.exception(f"Unexpected error retrieving {diagnostic_log_type.name}: {e}")
                return

        log.error(f"{diagnostic_log_type.name} logs failed after {max_retries} attempts.")
        return


@dataclass
class SubscriptionReportData:
    name: str
    endpoint: int
    attribute: TypedAttributePath.AttributeType
    value: str


class AttributeChangeAccumulator:
    def __init__(self, name: str, expected_attribute: ClusterObjects.ClusterAttributeDescriptor, output: queue.Queue):
        self._name = name
        self._output = output
        self._expected_attribute = expected_attribute

    def __call__(self, path: TypedAttributePath, transaction: SubscriptionTransaction):
        if path.AttributeType == self._expected_attribute:
            data = transaction.GetAttribute(path)

            name = self._name
            endpoint = path.Path.EndpointId
            attribute = path.AttributeType
            subscription_value = data

            log.info("Got subscription report on client %s for %s: %s" % (self.name, path.AttributeType, data))
            self._output.put(SubscriptionReportData(name, endpoint, attribute, subscription_value))

    @property
    def name(self) -> str:
        return self._name

def test_case_execution_result(matter_test_config: MatterTestConfig, runner: TestRunner):
    """
    Here we will determine the overall test case execution result, for normal/regular python scripts
    we will use the mobly's results object to determine the overall test case execution result.
    for Stress testing suite this function will use the stress_test_result attribute of matter_test_config
    to determine the test case execution result.
    """
    if hasattr(matter_test_config, "stress_test_result"):
        if matter_test_config.stress_test_result:
            log.info("Stress Test execution has Passed successfully as it matches threshold pass percentage")
        else:
            log.warning("Stress Test execution has been Failed as it does not match threshold pass percentage")
        return matter_test_config.stress_test_result
    else:
        return runner.results.is_all_pass


def run_augmented_matter_tests(test_class, *args, **kwargs):
    matter_test_config = parse_matter_test_args()
    append_stress_test_args(matter_test_config)
    hooks = InternalTestRunnerHooks()

    run_tests(test_class, matter_test_config, hooks)

def run_tests_no_exit(test_class: MatterBaseTest, matter_test_config: MatterTestConfig,
                      event_loop: asyncio.AbstractEventLoop, hooks: TestRunnerHooks,
                      default_controller=None, external_stack=None) -> bool:

    # NOTE: It's not possible to pass event loop via Mobly TestRunConfig user params, because the
    #       Mobly deep copies the user params before passing them to the test class and the event
    #       loop is not serializable. So, we are setting the event loop as a test class member.
    # CommissionDeviceTest.event_loop = event_loop
    test_class.event_loop = event_loop

    # Load test config file.
    test_config = generate_mobly_test_config(matter_test_config)
    test_config.testbed_name = os.path.join("MatterTest", matter_test_config.commissioning_method)

    # Parse test specifiers if exist.
    tests = None
    if len(matter_test_config.tests) > 0:
        tests = matter_test_config.tests

    if external_stack:
        stack = external_stack
    else:
        stack = MatterStackState(matter_test_config)

    with TracingContext() as tracing_ctx:
        for destination in matter_test_config.trace_to:
            tracing_ctx.StartFromString(destination)

        test_config.user_params["matter_stack"] = stash_globally(stack)

        # TODO: Steer to right FabricAdmin!
        # TODO: If CASE Admin Subject is a CAT tag range, then make sure to issue NOC with that CAT tag
        if not default_controller:
            default_controller = stack.certificate_authorities[0].adminList[0].NewController(
                nodeId=matter_test_config.controller_node_id,
                paaTrustStorePath=str(matter_test_config.paa_trust_store_path),
                catTags=matter_test_config.controller_cat_tags,
                dacRevocationSetPath=str(matter_test_config.dac_revocation_set_path),
            )
        test_config.user_params["default_controller"] = stash_globally(default_controller)

        test_config.user_params["matter_test_config"] = stash_globally(matter_test_config)
        test_config.user_params["hooks"] = stash_globally(hooks)

        # Execute the test class with the config
        ok = True

        test_config.user_params["certificate_authority_manager"] = stash_globally(stack.certificate_authority_manager)

        # Execute the test class with the config
        ok = True

        runner = TestRunner(log_dir=test_config.log_path,
                            testbed_name=test_config.testbed_name)
        # get_test_info(test_class, matter_test_config)
        with runner.mobly_logger():
            # if matter_test_config.commissioning_method is not None:
            #     runner.add_test_class(test_config, CommissionDeviceTest, None)

            # Add the tests selected unless we have a commission-only request
            if not matter_test_config.commission_only:
                runner.add_test_class(test_config, test_class, tests)

            if hooks:
                # Right now, we only support running a single test class at once,
                # but it's relatively easy to expand that to make the test process faster
                # TODO: support a list of tests
                hooks.start(count=1)
                # Mobly gives the test run time in seconds, lets be a bit more precise
                runner_start_time = datetime.now(timezone.utc)

            try:
                runner.run()
                ok = test_case_execution_result(matter_test_config, runner) and ok
                if matter_test_config.fail_on_skipped_tests and runner.results.skipped:
                    ok = False
            except TimeoutError:
                ok = False
            except signals.TestAbortAll:
                ok = False
            except Exception:
                log.exception('Exception when executing %s.', test_config.testbed_name)
                ok = False

    if hooks:
        duration = (datetime.now(timezone.utc) - runner_start_time) / timedelta(microseconds=1)
        hooks.stop(duration=int(duration))

    if not external_stack:
        async def shutdown():
            stack.Shutdown()
        # Shutdown the stack when all done. Use the async runner to ensure that
        # during the shutdown callbacks can use tha same async context which was used
        # during the initialization.
        event_loop.run_until_complete(shutdown())

    if ok:
        log.info("Final result: PASS !")
    else:
        log.error("Final result: FAIL !")
    return ok


def run_tests(test_class: MatterBaseTest, matter_test_config: MatterTestConfig,
              hooks: TestRunnerHooks, default_controller=None, external_stack=None) -> None:
    with asyncio.Runner() as runner:
        if not run_tests_no_exit(test_class, matter_test_config, runner.get_loop(),
                                 hooks, default_controller, external_stack):
            sys.exit(1)
