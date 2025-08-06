import asyncio
import copy
import importlib
import json
import logging
import os
import random
import shutil
import signal
import socket
import subprocess
import time
import traceback
import uuid
from statistics import mean
from uuid import uuid4

import chip.clusters as Clusters
from chip import ChipDeviceCtrl
from chip.clusters import Attribute
from chip.interaction_model import InteractionModelError, Status
from mobly import asserts, records, signals

from ...configs.config import TestConfig
from ..base_test_classes.models.test_results_model import *
from ..base_test_classes.test_results_record import *
from ..helper_libs import matter_qa_base_class_helpers
from ..helper_libs.analytics_graph_builder import build_analytics_graph_file
from ..helper_libs.augmented_matter_test_base import AugmentedMatterTestBase
from ..helper_libs.exceptions import *
from ..helper_libs.logger import qa_logger
from .models.test_results_model import *
from .test_result_db_observer import TestResultDBObserver
from .test_result_observable import TestResultObservable
from .test_result_observer import TestResultObserver

# Base TC logger variable
log = logging.getLogger("base_tc")


def format_exception_with_traceback(e):
    """
    Formats exception details into a JSON string containing the exception message and traceback.

    Args:
        e (Exception): The exception to format.

    Returns:
        str: A JSON string with the exception message and traceback.
    """
    exception_str = str(e)
    traceback_str = traceback.format_exc()
    return json.dumps({"exception_msg": exception_str, "traceback": traceback_str})


class MatterQABaseTestCaseClass(AugmentedMatterTestBase):
    """
    Base test case class for Matter QA testing, inheriting from MatterBaseTest.
    """

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self._init_attributes()  # Initialize essential attributes
        self._start_test()  # Start the test setup process

    def _init_attributes(self):
        """
        Initializes test attributes such as iteration counters, test result status,
        and configuration-related variables.
        """
        self.iteration_log_created = False  # Tracks if iteration log file is created
        self.fetch_dut_info_once_status = True  # Status for fetching DUT info
        self.test_step_number = 0  # Stores the test step number
        self.iteration_exception = None  # Stores exceptions during iterations
        self.iteration_begin_time = None  # Marks iteration start time
        self.iteration_end_time = None  # Marks iteration end time
        self.iteration_test_result = (
            TestResultEnums.TEST_RESULT_FAIL
        )  # Default test result
        self.total_number_of_iterations_passed = 0  # Passed iterations count
        self.total_number_of_iterations_failed = 0  # Failed iterations count
        self.total_number_of_iterations_error = 0  # Error iterations count
        self.list_of_iterations_failed = []  # List of failed iterations
        self.run_set_uuid = str(uuid4())  # Unique ID for the test run
        self.dut_info = None  # DUT information placeholder
        self.tcpdump_process_id = None  # TCP dump process ID
        self.test_started = False  # Tracks if the test has started
        self.sleep_duration_between_iterations = None  # Sleep duration in seconds

    def _start_test(self, **kwargs):
        """
        Starts the test by reading configurations, initializing test parameters,
        setting up logging, and subscribing to observers for test results.
        """
        try:
            # Read configurations from the config file
            self.test_config = self._config_reader(config=kwargs.get("test_config"))
            self._set_default_configuration()
            self.sleep_duration_between_iterations = (
                self.test_config.general_configs.sleep_duration_between_iterations
            )
            # Use test event trigger for factory reset if it is set in the config
            self.use_test_event_trigger_factory_reset = (
                self.test_config.general_configs.test_event_trigger_config.use_test_event_trigger_factory_reset
            )
            # Initialize configuration parameters
            self.test_config.current_failed_iteration = 0
            self.test_config.current_iteration = 1
            # this will be used to upload test results into a folder with test case name
            self.test_case_class = type(self).__name__
            self.test_config.controller_object = self.default_controller
            # Build the analytics dictionary for tracking test performance
            self.analytics_dict = copy.deepcopy(
                vars(getattr(self.test_config.general_configs, "analytics_parameters"))
            )
            self.analytics_dict.update({"iteration_duration": None})
            # Gather host information to build the records
            self.host_info = self._get_host_info()
            self.ci_info = None
            # add ci information if available in the config
            self.ci_config = getattr(self.test_config, "ci_config", None)
            # pass **self.ci_config to the model so that pydantic can unpack the complete dictionary
            if self.ci_config is not None:
                self.ci_config = copy.deepcopy(
                    vars(getattr(self.test_config, "ci_config"))
                )
                # TODO handle error conditions. if any of these configs do not exist
                self.ci_info = self._get_ci_info(self.ci_config)
            # create run set folder
            self.run_set_folder = self._create_run_set_folder()
            self.test_config.run_set_folder = self.run_set_folder
            # Initialize logger to create log file for every iteration
            self.qa_logger = qa_logger()
            self.dut = self._get_dut_obj()  # Create DUT object
            self.dut.start_test()
            # Overwrite factory reset config based on test event trigger setting
            self._overwrite_factory_reset_config()
            self.pass_percentage_threshold = (
                self.test_config.general_configs.pass_percentage_threshold
            )
            self.capture_tcp_dump_on_otbr = (
                self.test_config.otbr_device_config.capture_tcpdump_on_otbr
            )
            if self.capture_tcp_dump_on_otbr is True:
                self.otbr_object = self._get_otbr_object()  # Create OTBR object
            self.test_result_observable = (
                TestResultObservable()
            )  # Observable for test results
            self.summary_file = os.path.join(self.run_set_folder, "summary.json")
            self.test_result_observer = TestResultObserver(self.summary_file)
            self.test_result_observable.subscribe(self.test_result_observer)
            # Add a database observer if MongoDB configuration exists
            if (
                self.test_config.general_configs.mongodb_server_config.enable_mongodb_storage
                is True
            ):
                mongodb_server_config = getattr(
                    self.test_config.general_configs, "mongodb_server_config", None
                )
                if mongodb_server_config is None:
                    raise ValueError("mongodb_server_config is missing in the config")
                try:
                    self.test_result_db_observer = TestResultDBObserver(
                        mongodb_server_config
                    )
                    self.test_result_observable.subscribe(self.test_result_db_observer)
                except Exception as e:
                    if (
                        mongodb_server_config.continue_on_server_connection_fail
                        is False
                    ):
                        raise
                        # Prepare and notify initial summary record
            summary_record = matter_qa_base_class_helpers.build_initial_summary_record(
                self
            )
            self.test_results_record = TestExecutionResultsRecordModel(
                run_set_id=self.run_set_uuid, test_summary_record=summary_record
            )

            # this could be redundant as we are updting all info records in post iteration function.
            # self.test_results_record.ci_information_record = self.ci_info

            self.test_result_observable.notify(self.test_results_record)
            self.mobly_test_results_record = records.TestResultRecord(
                self.get_existing_test_names()[0], self.TAG
            )
            self.test_started = True  # Mark test as started
            # stress_test_result will be used to mark the test case execution's result as pass or fail to display in mobly results
            setattr(self.matter_test_config, "stress_test_result", False)
            # Handle keyboard interrupt to exit gracefully
            signal.signal(signal.SIGINT, self.handle_ctrl_c)
        except Exception as e:
            log.error(f"Failed to Start the test {e}")
            raise signals.TestAbortAll("Failed to Start the test")

    def _set_default_configuration(self):
        """Set default configurations if not already defined."""

        def set_default(obj, attr, value):
            """Helper function to set default attribute if missing."""
            if not hasattr(obj, attr):
                setattr(obj, attr, value)

        # Initialize general_configs.logging_config if missing
        # This will ensure that logging_config is always present
        set_default(
            self.test_config.general_configs,
            "logging_config",
            type("logging_config", (TestConfig,), {})(),
        )
        # Set default logging configurations if missing
        set_default(
            self.test_config.general_configs.logging_config,
            "capture_tcpdump_on_controller",
            True,
        )
        set_default(
            self.test_config.general_configs.logging_config, "copy_var_log", False
        )

        # Initialize test_event_trigger_config if missing
        set_default(
            self.test_config.general_configs,
            "test_event_trigger_config",
            type("test_event_trigger_config", (TestConfig,), {})(),
        )
        # Set default test event trigger configurations if missing
        set_default(
            self.test_config.general_configs.test_event_trigger_config,
            "use_test_event_trigger_factory_reset",
            False,
        )

        set_default(
            self.test_config.general_configs,
            "diagnostic_logs_config",
            type("general_configs", (TestConfig,), {})(),
        )
        set_default(
            self.test_config.general_configs.diagnostic_logs_config,
            "enable_diagnostic_log_capture",
            False,
        )

        # Set default for sleep duration if missing
        set_default(
            self.test_config.general_configs,
            "sleep_duration_between_iterations",
            random.randint(1, 5),
        )
        # Set default for pass_percentage_threshold if missing
        set_default(
            self.test_config.general_configs,
            "pass_percentage_threshold",
            TestResultsEnums.RECORD_TEST_PASS_THRESHOLD,
        )

        # Initialize otbr_device_config if missing
        set_default(
            self.test_config,
            "otbr_device_config",
            type("otbr_device_config", (TestConfig,), {})(),
        )
        set_default(
            self.test_config.otbr_device_config, "capture_tcpdump_on_otbr", False
        )

        # Initialize mongodb_server_config if missing
        set_default(
            self.test_config.general_configs,
            "mongodb_server_config",
            type("mongodb_server_config", (TestConfig,), {})(),
        )
        set_default(
            self.test_config.general_configs.mongodb_server_config,
            "enable_mongodb_storage",
            False,
        )

    def _overwrite_factory_reset_config(self):
        """
        Overwrites the factory reset configuration based on the test event trigger setting.
        """
        if self.use_test_event_trigger_factory_reset is True:
            setattr(self.dut.dut_config, "do_factory_reset_every_iteration", True)

    def perform_initial_factory_reset(self):
        """
        Perform an initial factory reset on the DUT as per the configuration.
        """
        try:
            if not self.use_test_event_trigger_factory_reset:
                self.dut.factory_reset_dut()
        except Exception as e:
            log.error(f"Failed to perform initial factory reset: {e}")
            raise DUTInteractionError("Failed to perform initial factory reset")

    def _config_reader(self, config=None):
        """
        Reads and initializes the test configuration.
        Args:
            config: Optional configuration input.
        Returns:
            TestConfig: An instance of the test configuration.
        """
        test_config = TestConfig(
            self.matter_test_config.reliability_tests_config
        )  # Load base config
        test_config = self._overwrite_test_config(
            test_config
        )  # Apply test case-specific overrides
        return test_config

    def _overwrite_test_config(self, test_config):
        """
        Overwrites default test configuration with test case-specific parameters.
        Args:
            test_config (TestConfig): The initial test configuration.
        Returns:
            TestConfig: The updated test configuratio
        """
        if hasattr(test_config, "test_case_config"):
            test_case_config = getattr(test_config, "test_case_config")
            if hasattr(test_case_config, type(self).__name__):
                test_case_specific_config = getattr(
                    test_case_config, type(self).__name__
                )
                # loop on all attributes in the test_case_config toreplace them in general config
                for config_attribute in test_case_specific_config.__dict__:
                    setattr(
                        test_config.general_configs,
                        config_attribute,
                        getattr(test_case_specific_config, config_attribute),
                    )

        return test_config

    def _get_ci_info(self, ci_config):
        try:
            # return pydantic model dict
            return CIInformationRecordModel(**ci_config)
        except Exception as e:
            log.error("Failed to get the host informnation {e}".format(e))
            raise signals.TestAbortAll("Failed to get host info")

    def _get_host_info(self):
        """
        Retrieves host system information such as hostname, IP address, and MAC address.
        Returns:
            HostInformationRecordModel: An object containing host information.
        """
        try:
            hostname = socket.gethostname()  # Get the hostname of the system
            host_ip = socket.gethostbyname(
                hostname
            )  # Resolve the hostname to an IP address
            # Generate MAC address from UUID node value
            host_mac = ":".join(
                [
                    "{:02x}".format((uuid.getnode() >> elements) & 0xFF)
                    for elements in range(0, 2 * 6, 2)
                ]
            )
            return HostInformationRecordModel(
                host_name=hostname, ip_address=host_ip, mac_address=host_mac
            )
        except Exception as e:
            log.error("Failed to get the host informnation {e}".format(e))
            raise signals.TestAbortAll("Failed to get host info")

    def _create_run_set_folder(self):
        """
        Creates a folder structure for storing logs and results for the test run.We are re-using the directories created by mobly framework
        mobly will create a runset id and folder like '03-19-2024_12-36-26-432'
        iteration wise data will be stored in the directory <log_path>/MatterTest/<run-set>/<test_case_name>
        if this path does not exist then current directory will be used.

        self.root_output_path -> created by mobly will have structure of <log_path>/MatterTest/<run-set>
                self.TAG -> created by mobly will have test_class_name

        Returns:
            str: The path to the created run set folder.
        """
        try:
            run_set_folder_path = os.path.join(
                self.root_output_path, self.TAG
            )  # Default run set path
            if not os.path.exists(run_set_folder_path):
                # Create a timestamped folder in the current working directory
                run_set_folder_path = os.path.join(
                    os.getcwd(),
                    datetime.datetime.now().strftime("%d-%m-%Y_%H-%M-%S-%f"),
                    self.TAG,
                )
                os.mkdir(run_set_folder_path)  # Create the directory
            self.test_config.runset_folder_path = (
                run_set_folder_path  # Update config with folder path
            )
            return run_set_folder_path
        except Exception as e:
            log.error("Failed to create a log file folder {e}".format(e))
            raise signals.TestAbortAll("Failed to create run set folder")

    def _create_iteration_log_file(self, iteration_count):
        """
        Creates a log file for a specific iteration of the test case.
        Args:
            iteration_count (int): The iteration number.
        Raises:
            SystemExit: If log file creation fails.
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        try:
            self.iter_log_path = os.path.join(self.run_set_folder, str(iteration_count))
            if not os.path.exists(self.iter_log_path):
                os.makedirs(self.iter_log_path)
            log_filename = os.path.join(
                self.iter_log_path,
                f"controller_log_iteration_{iteration_count}_{timestamp}.log",
            )
            self.iteration_log = self.qa_logger.create_log_file(log_filename)
            log.info("Started Iteration {}".format(iteration_count))
            self.iteration_log_created = True
            self.test_config.iter_log_path = self.iter_log_path
        except Exception as e:
            log.error("Failed to create iteration log file {e}".format(e))
            raise signals.TestAbortAll("Failed to create iteration log file")

    def _get_dut_obj(self):
        """
        Retrieves the Device Under Test (DUT) object.
        Returns:
            DUT object: The DUT object created from the platform module.
        """
        module = self._import_platform()
        return self._create_dut_obj(module)

    def _import_platform(self):
        """
        Import platform-specific DUT module dynamically based on configuration.
        Returns:
            module: The imported DUT module.
        Raises:
            SystemExit: If platform configuration is invalid or module fails to load.
        """
        try:
            platform = self.test_config.general_configs.platform_execution
            if hasattr(self.test_config.dut_config, platform):
                dut_platform = getattr(self.test_config.dut_config, platform)
                # import platform specific module
                module = importlib.import_module(dut_platform.module)
                return module
            else:
                raise signals.TestAbortAll("DUT module not available")
        except Exception as e:
            log.error("Error loading dut module: {}".format(e))
            traceback.print_exc()
            raise signals.TestAbortAll("Failed to import the platform")

    def _create_dut_obj(self, module):
        """
        Creates and returns a DUT object using the specified module.
        Args:
            module: The module used to create the DUT object.
        Returns:
            DUT object: The created DUT object.
        """
        return module.create_dut_object(self.test_config)

    def _get_otbr_object(self, *args, **kwargs):
        """
        Import and instantiate the OTBR object based on the configuration.

        Returns:
            Any: The instantiated OTBR object.

        Raises:
            ValueError: If the required configuration for the OTBR agent is missing.
        """
        otbr_device_config = getattr(self.test_config, "otbr_device_config", None)
        if otbr_device_config is None:
            raise ValueError("OTBR device configuration is missing in the test config.")

        # Retrieve the OTBR agent from the device configuration
        otbr_agent = getattr(otbr_device_config, "otbr_agent", None)
        if otbr_agent is None:
            raise ValueError(
                "OTBR agent is not specified in the OTBR device configuration."
            )

        # Retrieve the OTBR platform configuration for the specified agent
        otbr_platform = getattr(otbr_device_config, otbr_agent, None)
        if otbr_platform is None:
            raise ValueError(
                f"OTBR platform configuration for agent '{otbr_agent}' is missing."
            )
        module = importlib.import_module(otbr_platform.module)
        otbr_object = module.create_otbr_object(self.test_config)
        return otbr_object

    def handle_ctrl_c(self, signum, frame):
        """
        Handle Ctrl+C signal for graceful test cleanup and exit.
        """
        log.info("Ctrl+C pressed. Cleaning up gracefully...")
        self.end_of_test(test_aborted=True)
        raise signals.TestAbortAll("Execution is stopped by Ctrl+C")

    def do_factory_reset_every_iteration(self):
        """
        Return the do_factory_reset_every_iteration from Config
        """

        if hasattr(self.dut.dut_config, "do_factory_reset_every_iteration"):
            return getattr(self.dut.dut_config, "do_factory_reset_every_iteration")
        return True

    def _get_trigger_id_for_factory_reset(self):
        """
        Get the factory reset trigger ID from the configuration.
        Returns:
            str: The trigger ID to use for the factory reset.
        Raises:
            TestAbortAll: if the trigger ID is missing from the config.
        """
        test_event_trigger_config = (
            self.test_config.general_configs.test_event_trigger_config
        )
        trigger_id = getattr(
            test_event_trigger_config, "factory_reset_trigger_id", None
        )

        if trigger_id is None:
            raise signals.TestAbortAll(
                "Trigger ID for factory reset is missing in the config. "
                "Please provide a valid 'factory_reset_trigger_id' for the factory reset event."
            )

        log.info(f"Trigger ID for factory reset: {trigger_id}")
        return trigger_id

    def _get_enable_key(self):
        """
        Retrieve the optional enable key for the test event trigger.
        Returns:
            bytes: The enable key as bytes if present, else None.
        """
        test_event_trigger_config = (
            self.test_config.general_configs.test_event_trigger_config
        )
        enable_key = getattr(test_event_trigger_config, "enable_key", None)
        log.info(f"Enable key for factory reset: {enable_key}")
        if enable_key is not None:
            return bytes.fromhex(enable_key)
        return None

    async def perform_factory_reset_dut(self):
        """
        Perform factory reset on the DUT as per the configuration.
        Uses test event trigger if configured, otherwise uses default DUT factory reset.

        This method checks the configuration flag 'use_test_event_trigger_factory_reset'
        to determine which factory reset method to use:
        - If True: Uses test event trigger mechanism for factory reset
        - If False: Uses the standard DUT factory reset method

        Raises:
            Exception: If factory reset operation fails
        """
        log.info("Performing factory reset on DUT")

        try:
            # Check configuration to determine which factory reset method to use
            if self.use_test_event_trigger_factory_reset is True:
                # Skip factory reset for the first iteration
                if self.test_config.current_iteration != 1:
                    log.info("Using test event trigger for factory reset")
                    # Ensure the test event trigger is available
                    trigger_id = self._get_trigger_id_for_factory_reset()
                    enable_key = self._get_enable_key()
                    await self.send_test_event_triggers(
                        eventTrigger=trigger_id, enableKey=enable_key
                    )
            else:
                # Use the default DUT factory reset method
                log.info("Using default DUT factory reset method")
                self.dut.factory_reset_dut()

        except Exception as e:
            # Log the error with full traceback for debugging purposes
            log.error(f"Factory reset failed: {e}", exc_info=True)
            raise DUTInteractionError(f"Failed to perform factory reset on DUT : {e}")

    def pre_iteration(self, *args, **kwargs):
        """
        Perform setup at the beginning of each iteration.
        Resets analytics dictionary, test result, and starts capturing TCP dump if needed.
        """

        def reset_analytics_dict(dictionary):
            # Reset all dictionary values to None
            for key in dictionary:
                dictionary[key] = None

        # Stop TCP dump capture if it was started in the previous iteration
        self.stop_capture_tcpdump()

        self.iteration_begin_time = datetime.datetime.now()
        self.test_step_number = 0
        reset_analytics_dict(self.analytics_dict)
        self.iteration_test_result = TestResultEnums.TEST_RESULT_FAIL
        if not self.iteration_log_created:
            self._create_iteration_log_file(self.test_config.current_iteration)
        # Call pre-iteration setup for the DUT
        self.dut.pre_iteration_loop(*args, **kwargs)
        if self.capture_tcp_dump_on_otbr is True:
            self.otbr_object.start_tcp_dump_capture()
        # Add the iteration to the requested results
        self.results.requested.append(self.mobly_test_results_record)
        self.capture_tcp_dump()

    def capture_tcp_dump(self):
        """
        Start capturing network traffic using tcpdump if configured.
        """
        if (
            self.test_config.general_configs.logging_config.capture_tcpdump_on_controller
            is True
        ):
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            try:
                # Generate filename for the TCP dump capture
                tcp_dump_filename = os.path.join(
                    self.iter_log_path, f"controller_tcpdump_{timestamp}.pcap"
                )
                tcpdump_command = [
                    "tcpdump",
                    "-i",
                    "any",
                    "-w",
                    tcp_dump_filename,
                    "port",
                    "not",
                    "22",
                ]
                # Start tcpdump as a subprocess
                self.tcpdump_process_id = subprocess.Popen(tcpdump_command)
                log.info(f"Started tcpdump with PID: {self.tcpdump_process_id}")

            except Exception as e:
                log.error("Failed to create tcpdump {e}".format(e))

    def __copy_var_logs(self):
        """
        Copy log files from /var/log to the iteration log directory if the test fails.
        """
        if (
            self.test_config.general_configs.logging_config.copy_var_log is True
            and self.iteration_test_result == TestResultEnums.TEST_RESULT_FAIL
        ):
            for (
                var_log_file_name
            ) in self.test_config.general_configs.logging_config.var_log_filenames:
                try:
                    # Construct source and destination file paths
                    source_path = os.path.join("/var/log", var_log_file_name)
                    destination_path = os.path.join(
                        self.iter_log_path, var_log_file_name
                    )
                    if os.path.isfile(source_path):
                        shutil.copyfile(source_path, destination_path)
                except Exception as e:
                    log.error(f"Failed to copy Reason:: {e}", exc_info=True)

    def _create_iteration_json_file(self, iteration_record=None):
        """
        Create a JSON file to record details of the iteration.
        """
        iteration_json_file = os.path.join(self.iter_log_path, "iteration.json")
        with open(iteration_json_file, "w") as file_write:
            json.dump(
                iteration_record,
                file_write,
                indent=4,
                default=self.custom_json_serializer,
            )

    def custom_json_serializer(self, obj):
        """
        Custom JSON serializer for datetime objects.
        Args:
            obj: The object to serialize.
        Returns:
            str: ISO format of datetime objects.
        """
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()

    def __iteration_results_record_created(self):
        """
        Update the iteration  JSon
        """
        # set this flag to create log in next iteration
        self.iteration_log_created = False
        self.iteration_end_time = datetime.datetime.now()
        test_exec_record = (
            matter_qa_base_class_helpers.update_test_results_post_iteration(
                self
            ).model_dump()
        )
        self._create_iteration_json_file(
            test_exec_record["list_of_iteration_records"][0]
        )

    def update_mobly_results_record_and_summary_json_data(self):
        self.__iteration_results_record_created()
        self.test_result_observable.notify(self.test_results_record)
        # Updating iteration results to the self.results mobly object
        self.results.executed.append(self.mobly_test_results_record)
        if self.iteration_test_result == TestResultEnums.TEST_RESULT_FAIL:
            self.results.failed.append(self.mobly_test_results_record)
        else:
            self.results.passed.append(self.mobly_test_results_record)

    def mark_iteration_failure_sync_mobly_and_summary_data(
        self, iteration_failure_message
    ):
        """
        The usage of this function should be made when executing a script we encounter a critical exception
        in the script execution flow which will make the flow to exit and before such event we will perform proper
        reporting to mobly results and summary.json file, to avoid improper/false messages to execution console and
        Stress Test UI
        """
        self.update_iteration_result(
            iteration_result=TestResultEnums.TEST_RESULT_FAIL,
            execption=iteration_failure_message,
        )
        self.test_config.current_failed_iteration = self.test_config.current_iteration
        self.update_mobly_results_record_and_summary_json_data()

    async def post_iteration(self, *args, **kwargs):
        """
        Perform cleanup and record updates at the end of each iteration.
        """
        if self.iteration_test_result == TestResultEnums.TEST_RESULT_FAIL:
            self.test_config.current_failed_iteration = (
                self.test_config.current_iteration
            )
        log.info(
            "Iteration {} {} :".format(
                self.test_config.current_iteration, self.iteration_test_result
            )
        )
        self.enable_diag_log_capture = getattr(
            self.test_config.general_configs.diagnostic_logs_config,
            "enable_diagnostic_log_capture",
            False,
        )
        self.bdx_transfer_timeout_seconds = getattr(
            self.test_config.general_configs.diagnostic_logs_config,
            "bdx_transfer_timeout_seconds",
            5,
        )
        if self.enable_diag_log_capture:
            await self.retrieve_multiple_diagnostic_logs()
        self.__copy_var_logs()
        self.stop_capture_tcpdump()
        self.dut.post_iteration_loop(*args, **kwargs)
        if self.capture_tcp_dump_on_otbr is True:
            self.otbr_object.stop_tcp_dump_capture()
            self.otbr_object.save_tcpdump_capture_file()
        self.qa_logger.close_log_file(self.iteration_log)
        self.update_mobly_results_record_and_summary_json_data()

    def stop_capture_tcpdump(self):
        """
        Stops the tcpdump capture process if it is running.
        Handles timeout and other exceptions during termination.
        """
        if (
            self.test_config.general_configs.logging_config.capture_tcpdump_on_controller
            is True
        ):
            try:
                if self.tcpdump_process_id is not None:
                    self.tcpdump_process_id.terminate()
                    self.tcpdump_process_id.wait(timeout=5)
                    log.info("stopped tcpdump capture")
            except subprocess.TimeoutExpired as e:
                log.info("Killing TCPDump process as it took too long")
                try:
                    self.tcpdump_process_id.kill()
                    self.tcpdump_process_id.wait(timeout=5)
                    if self.tcpdump_process_id.poll() is None:
                        log.info("Stopped tcpdump capture")
                    else:
                        log.info("Process still running could not kill tcpdump process")
                except subprocess.TimeoutExpired as e:
                    log.info(
                        "TCPDump process has took too long, exception raised is {}".format(
                            e
                        )
                    )
                except Exception as e:
                    log.error(e, exc_info=True)
            except Exception as e:
                log.error(e, exc_info=True)

    def get_test_result(self, *args, **kwargs):
        """executed
        Determines the overall test result based on the pass percentage.

        Returns:
            bool: True if the pass percentage meets the threshold, False otherwise.
        """
        # Count the number of executed and passed tests
        executed_tests = len(self.results.executed)
        if (
            executed_tests == 0
        ):  # Ensure tests were executed before calculating the percentage
            return False
        try:
            if executed_tests > 1:
                last_record_in_executed_list: TestResultRecord = (
                    self.results.executed.pop(-1)
                )
                match last_record_in_executed_list.result:
                    case records.TestResultEnums.TEST_RESULT_PASS:
                        self.results.passed.remove(last_record_in_executed_list)
                    case records.TestResultEnums.TEST_RESULT_FAIL:
                        self.results.failed.remove(last_record_in_executed_list)
                    case records.TestResultEnums.TEST_RESULT_ERROR:
                        self.results.error.remove(last_record_in_executed_list)
                    case records.TestResultEnums.TEST_RESULT_SKIP:
                        self.results.skipped.remove(last_record_in_executed_list)

            # Calculate pass percentage
            pass_percentage = (
                len(self.results.passed) / len(self.results.executed)
            ) * 100
            test_result = pass_percentage >= self.pass_percentage_threshold
            # Update the overall threshold of stress test execution by updating the stress_test_result attribute of matter_test_config
            self.matter_test_config.stress_test_result = test_result
            return test_result
        except Exception as e:
            log.error(f"Failed to adjust test results: {str(e)}")
            return False

    def teardown_class(self):
        """
        this function will be called at the end of the test run by mobly to perform cleanup
        and call the end_of_test method of the MatterQABaseTestCaseClass so that all scripts
        will be able to use this by default
        """
        self.end_of_test()
        super().teardown_class()

    def end_of_test(self, *args, **kwargs):
        """
        Marks the end of the test case execution, setting the status and results appropriately.
        Stops tcpdump capture if necessary.
        Args:
            *args: Additional arguments.
            **kwargs: Additional keyword arguments.
        """

        if "test_aborted" in kwargs:
            self.test_results_record.test_summary_record.test_case_status = (
                TestResultsEnums.RECORD_TEST_IS_ABORTED
            )
            self.results.skipped.append(self.mobly_test_results_record)
            self.results.executed.append(self.mobly_test_results_record)
            self.dut.stop_logging()
            self.__iteration_results_record_created()
        else:
            self.test_results_record.test_summary_record.test_case_status = (
                TestResultsEnums.RECORD_TEST_COMPLETED
            )
        self.dut.end_test()
        if self.use_test_event_trigger_factory_reset is True:
            # Perform factory reset using test event trigger at the end of the test
            log.info(
                "Performing factory reset at the end of the test using test event trigger"
            )
            try:
                async_loop = asyncio.get_running_loop()
                # If we're in an event loop, schedule the coroutine
                factory_reset_task = async_loop.create_task(
                    self.perform_factory_reset_dut()
                )
                # wait for the task to finish if needed:
                async_loop.run_until_complete(factory_reset_task)
            except RuntimeError:
                # No running event loop, use the default asyncio.run
                asyncio.run(self.perform_factory_reset_dut())
        # stop capturing tcpdump in case we land in here bcoz of exception
        self.stop_capture_tcpdump()
        # Get the overall test result
        test_run_result = self.get_test_result(self.results)
        if test_run_result:
            self.test_results_record.test_summary_record.test_case_result = (
                TestResultsEnums.RECORD_ITERATION_RESULT_PASS
            )
        else:
            self.test_results_record.test_summary_record.test_case_result = (
                TestResultsEnums.RECORD_ITERATION_RESULT_FAIL
            )
        self.test_results_record.test_summary_record.test_case_ended_at = (
            datetime.datetime.now()
        )
        mean_of_analytics = self.calculate_mean_of_analytics(self.summary_file)
        self.test_results_record.test_summary_record.mean_of_analytics = (
            mean_of_analytics
        )
        self.test_result_observable.notify(self.test_results_record)
        # this is to stop the async upload to mongodb
        # self.test_result_observable.notify(None)
        self.create_chart_with_summary_file(self.summary_file)

    def calculate_mean_of_analytics(self, summary_file):
        summary = {}
        try:
            with open(summary_file, "r") as f:
                data = json.load(f)

            failed_iterations = set(
                data["test_summary_record"].get("list_of_iterations_failed", [])
            )

            analytics_fields = data["test_summary_record"].get(
                "analytics_parameters", []
            )
            valid_records = []

            for record in data["list_of_iteration_records"]:
                iter_num = record["iteration_number"]
                result = record["iteration_data"]["iteration_tc_execution_data"][
                    "iteration_result"
                ]

                if result == "PASS" and iter_num not in failed_iterations:
                    valid_records.append(
                        record["iteration_data"]["iteration_tc_analytics_data"]
                    )

            if valid_records:
                for key in analytics_fields:
                    try:
                        values = [rec[key] for rec in valid_records if key in rec]
                        values = list(filter(lambda x: x is not None, values))
                        if len(values) > 0:
                            summary[key] = mean(values)
                        else:
                            log.warning(f"Value set for analytics key '{key}' is empty")
                    except Exception as e:
                        log.error(
                            f"Skipping {key} due to error: {str(e)}", exc_info=True
                        )

            return summary
        except Exception as e:
            log.error(f"Failed to get Mean of analytics params: {str(e)}")
            return summary

    def update_iteration_result(
        self, iteration_result: TestResultEnums, execption=None
    ):
        """
        Updates the result of the current iteration based on the provided status.
        Args:
            iteration_result (TestResultEnums): The result of the iteration (PASS/FAIL).
            execption (Exception, optional): The exception raised, if any.
        """
        if iteration_result == TestResultEnums.TEST_RESULT_FAIL:
            self.iteration_exception = format_exception_with_traceback(execption)
            self.iteration_test_result = TestResultEnums.TEST_RESULT_FAIL
        else:
            self.iteration_test_result = TestResultEnums.TEST_RESULT_PASS

    def iterate_tc(iterations=1):
        """
        Decorator to handle test case iteration, including pre- and post-iteration steps.
        Args:
            iterations (int): Number of iterations for the test case.
        Returns:
            Function: The wrapped test case function.
        """

        def decorator(func):
            async def wrapper(self, *args, **kwargs):
                # Reset the mobly's requested attribute of results to match stress test execution results
                self.results.requested.clear()
                for current_iteration in range(1, iterations + 1):
                    self.test_config.current_iteration = current_iteration
                    self.pre_iteration(*args, **kwargs)
                    try:
                        await func(*args, **kwargs)
                        time.sleep(
                            self.test_config.general_configs.sleep_duration_between_iterations
                        )
                    except TestCaseExit as e:
                        log.error("Exiting the loop", exc_info=True)
                        # To Exit the loop and kill the DUT
                        self.test_config.current_iteration = iterations
                        break
                    except ReliabiltyTestError as e:
                        log.info(
                            "Exception has been raised, failed iteration {}".format(
                                self.test_config.current_iteration
                            )
                        )
                        self.update_iteration_result(
                            iteration_result=TestResultEnums.TEST_RESULT_FAIL,
                            execption=e,
                        )
                        log.error(e, exc_info=True)
                    await self.post_iteration(*args, **kwargs)

            return wrapper

        return decorator

    async def fetch_analytics_from_dut(
        self, dev_ctrl: ChipDeviceCtrl = None, node_id: int = None, endpoint: int = 0
    ):
        """
        Fetch analytics data from the Device Under Test (DUT).
        Args:
            dev_ctrl (ChipDeviceCtrl, optional): The device controller object.
            node_id (int, optional): The node ID of the DUT.
            endpoint (int, optional): The endpoint to query analytics data from.
        Raises:
            Exception: If attribute reading fails or analytics parameters are invalid.
        """
        # Check if DUT info needs to be fetched
        if self.fetch_dut_info_once_status is True:
            # Fetch DUT info and update status
            self.dut_info = await matter_qa_base_class_helpers.fetch_dut_info_once(
                self, dev_ctrl=dev_ctrl, node_id=node_id, endpoint=endpoint
            )
            self.fetch_dut_info_once_status = False
        # Use default controller and node ID if not provided
        if dev_ctrl is None:
            dev_ctrl = self.default_controller
        if node_id is None:
            node_id = self.dut_node_id

        analytics_params = getattr(
            self.test_config.general_configs, "analytics_parameters"
        )
        if analytics_params is not None:
            # Analytics_params is python object so read attributes using vars
            analytics_params_dict = vars(analytics_params)
            for analytics_name, analytics_attribute in analytics_params_dict.items():
                # Split the attribute of the analytics to get class instance of attribute
                analytics_attribute_components = analytics_attribute.attribute.split(
                    "."
                )
                analytics_cluster = Clusters
                for component in analytics_attribute_components:
                    try:
                        # Navigate through attribute components to get the final cluster
                        analytics_cluster = getattr(analytics_cluster, component)
                    except Exception as e:
                        # Break on error while Reading attributes
                        break
                try:
                    # Attempt to read the attribute from the DUT
                    response = await self.read_single_attribute(
                        dev_ctrl=dev_ctrl,
                        node_id=node_id,
                        endpoint=analytics_attribute.end_point,
                        attribute=analytics_cluster,
                    )
                    if isinstance(response, Attribute.ValueDecodeFailure):
                        log.error(f"Value decode error: {response}")
                        response = None
                except Exception as e:
                    log.error("Read attribute function timedout : {}".format(e))
                    self.iteration_exception = format_exception_with_traceback(e)
                    response = None
                except InteractionModelError as e:
                    # Handle specific interaction model errors
                    response = None

                # Update the analytics dictionary with the fetched data
                self.analytics_dict.update({analytics_name: response})

    async def perform_initial_commission_with_dut(self):
        """
        This function performs initial commission with DUT. In most stress Test scenarios when the DUT needs to be commissioned only
        once, this function should be used as in such scenarios during stress testing and
        in the event of a failing to pair the 'test_case_status' will be marked as 'Test Completed',
        'test_case_result' will be marked as 'FAIL'
        and few other vital information will be updated in summary.json when test case exits
        Returns:
        None
        """
        pairing_status = await self.pair_dut()
        if pairing_status:
            log.info(
                "Device Has been commissioned proceeding forward with next execution steps"
            )
        else:
            self.test_results_record.test_summary_record.test_case_status = (
                TestResultsEnums.RECORD_TEST_COMPLETED
            )
            self.test_results_record.test_summary_record.test_case_result = (
                TestResultsEnums.RECORD_ITERATION_RESULT_FAIL
            )
            self.test_results_record.test_summary_record.test_case_ended_at = (
                datetime.datetime.now()
            )
            self.test_result_observable.notify(self.test_results_record)
            asserts.fail(
                f"Pairing with DUT has failed Reason {pairing_status}, exiting from test case"
            )

    def delay_between_stress_test_operations(self, delay_between_operations=0):
        """

        this function can be used to delay between stress test operations. It will read from configFile the key
        'delay_between_stress_test_operations' and provide delay, if the key is missing then it will default to 5 seconds.
        for example the DUT may take 5 seconds after pairing operation to have settle down before unpairing is initiated
        this function can be used efficiently to be provide such relax time to the DUT.
        Args:
            delay_between_operations: user can use this argument inside the script to overwrite the config values.

        Returns:
            no data returned
        """
        if hasattr(
            self.test_config.general_configs, "delay_between_stress_test_operations"
        ):
            delay_between_operations = (
                self.test_config.general_configs.delay_between_stress_test_operations
            )
        log.info(
            f"adding delay of {delay_between_operations} seconds between stress test operations"
        )
        time.sleep(delay_between_operations)

    def create_chart_with_summary_file(self, summary_file):
        analytics_graph_html_libs_path = None
        analytics_graph_file_name = None
        try:
            summary_file_fp = open(summary_file, "r")
            summary_json = TestExecutionResultsRecordModel(**json.load(summary_file_fp))
            summary_file_fp.close()
            # Generate file name for the HTML file
            file_name = (
                summary_json.test_summary_record.platform
                + "_"
                + summary_json.test_summary_record.commissioning_method
                + "_"
                + "line_charts.html"
            )
            analytics_graph_file_name = os.path.join(self.run_set_folder, file_name)
            analytics_graph_html_libs_path = build_analytics_graph_file(
                analytics_graph_file_name, summary_json, self.run_set_folder
            )

        except IOError as e:
            log.error(
                f"Read or Write operation for building html graph file Failed!! Reason: {e}",
                exc_info=True,
            )
        except Exception as e:
            log.error(
                f"Creating analytics chart with summary file Failed!! Reason: {e}",
                exc_info=True,
            )

        # Copy the HTML file to the CI workspace folder
        try:
            self.ci_config = getattr(self.test_config, "ci_config", None)
            ci_test_results_path_in_ws = getattr(
                self.ci_config, "ci_test_results_path_in_ws", None
            )
            #  check if all variables used for copying data to ci workspace are not having None by using python's all() function
            if all(
                [
                    ci_test_results_path_in_ws,
                    analytics_graph_file_name,
                    analytics_graph_html_libs_path,
                ]
            ):
                dest = os.path.expanduser(ci_test_results_path_in_ws)
                # expected format TC_Pair_test_results , This should match with the test case name used in CI
                test_results_folder = os.path.join(
                    dest, self.test_case_class + "_test_results"
                )
                if not os.path.exists(test_results_folder):
                    os.makedirs(test_results_folder, exist_ok=True)
                    log.info(f"Created directory: {test_results_folder}")
                ci_workspace_graph_libs_path = os.path.join(
                    test_results_folder, "analytics_graph_html_libs"
                )
                shutil.copytree(
                    analytics_graph_html_libs_path,
                    ci_workspace_graph_libs_path,
                    dirs_exist_ok=True,
                )
                shutil.copy(analytics_graph_file_name, test_results_folder)
                shutil.copy(summary_file, test_results_folder)
                log.info(
                    f"File copied from {analytics_graph_file_name} to {test_results_folder}"
                )
            elif ci_test_results_path_in_ws is not None:
                log.warning(
                    f"cannot copy graph to CI workspace as some directories are not valid "
                    f"'CI Workspace Directory Path' is {ci_test_results_path_in_ws}"
                    f"'Html Libs Dir for graphs' is {analytics_graph_html_libs_path}"
                    f"'Analytics graph File path' is {analytics_graph_file_name}"
                )

        except Exception as e:
            log.error(f"Error occurred: {e}")

    async def retrieve_multiple_diagnostic_logs(self):
        """
        Retrieve multiple types of diagnostic logs and save them to files.

        Returns:
            None
        """
        log_type_map = {
            "crash_log": Clusters.DiagnosticLogs.Enums.IntentEnum.kCrashLogs,
            "end_user_log": Clusters.DiagnosticLogs.Enums.IntentEnum.kEndUserSupport,
            "network_diagnosis_log": Clusters.DiagnosticLogs.Enums.IntentEnum.kNetworkDiag,
        }
        results = {}
        try:
            for log_type, intent_enum in log_type_map.items():
                logging.info(f"Retrieving diagnostic {log_type}")
                filename = f"{log_type}.txt"
                file_path = os.path.join(self.iter_log_path, filename)
                try:
                    await self.retrieve_diagnostic_logs_from_device(
                        self.matter_test_config.endpoint,
                        self.test_config,
                        file_path,
                        intent_enum,
                        bdx_transfer_timeout=self.bdx_transfer_timeout_seconds,
                    )
                except Exception as e:
                    logging.error(f"Failed to retrieve {log_type}: {e}")
        except AttributeError as e:
            logging.error("Diagnostic logs config is missing or malformed: %s", e)
        except Exception as e:
            logging.error(
                "Unexpected error in retrieve_multiple_diagnostic_logs: %s", e
            )
