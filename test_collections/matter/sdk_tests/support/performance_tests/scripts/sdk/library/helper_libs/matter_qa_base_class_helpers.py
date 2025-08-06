import datetime
import json
import logging
import os
from enum import Enum, auto

import chip.clusters as Clusters
from chip import ChipDeviceCtrl
from matter_qa.library.base_test_classes.test_results_record import *
from matter_qa.library.base_test_classes.models.test_results_model import *

log = logging.getLogger("base_tc")

def build_initial_summary_record(self):
    # analytics_parameters is list of analytics 
    summary_record = SummaryTestResultRecordModel(test_suite_name= self.test_suite_name,
                                                    test_case_name = self.tc_name,
                                                    test_case_id = self.tc_id,
                                                    test_case_class = type(self).__name__,
                                                    test_case_begined_at = datetime.datetime.now(),
                                                    total_number_of_iterations = self.test_config.general_configs.number_of_iterations,
                                                    test_case_status = TestResultsEnums.RECORD_TEST_IN_PROGRESS,
                                                    test_case_result= TestResultsEnums.RECORD_TEST_IN_PROGRESS,
                                                    platform = self.test_config.general_configs.platform_execution,
                                                    commissioning_method = self.matter_test_config.commissioning_method,
                                                    analytics_parameters = self.analytics_dict.keys()).model_dump()

    return summary_record


async def fetch_dut_info_once(self, dev_ctrl: ChipDeviceCtrl = None, node_id: int = None, endpoint: int = 0):
    if dev_ctrl is None:
        dev_ctrl = self.default_controller
    if node_id is None:
        node_id = self.dut_node_id
    
    default_info_attributes = {
        DUTInformationRecordEnums.RECORD_PRODUCT_NAME: Clusters.BasicInformation.Attributes.ProductName,
        DUTInformationRecordEnums.RECORD_VENDOR_NAME: Clusters.BasicInformation.Attributes.VendorName,
        DUTInformationRecordEnums.RECORD_VENDOR_ID: Clusters.BasicInformation.Attributes.VendorID,
        DUTInformationRecordEnums.RECORD_HARDWARE_VERSION: Clusters.BasicInformation.Attributes.HardwareVersionString,
        DUTInformationRecordEnums.RECORD_SOFTWARE_VERSION: Clusters.BasicInformation.Attributes.SoftwareVersionString,
        DUTInformationRecordEnums.RECORD_PRODUCT_ID: Clusters.BasicInformation.Attributes.ProductID,
        DUTInformationRecordEnums.RECORD_SERIAL_NUMBER: Clusters.BasicInformation.Attributes.SerialNumber}
    
    dut_info_record = {}
    for k, v in default_info_attributes.items():
        try:
            response = await self.read_single_attribute_check_success(cluster = Clusters.Objects.BasicInformation,dev_ctrl=dev_ctrl, node_id=node_id,
                                                        endpoint=endpoint,
                                                        attribute=v)
        except Exception as e:
            log.error("Read attribute function timedout : {}".format(e))
            self.iteration_exception = str(e)
            response = "default"
        dut_info_record.update({k: response})
    return DUTInformationRecordModel.model_validate(dut_info_record)

def update_test_results_post_iteration(self):

    if self.iteration_test_result == TestResultsEnums.RECORD_ITERATION_RESULT_PASS:
        self.total_number_of_iterations_passed = self.total_number_of_iterations_passed + 1
    else:
        self.total_number_of_iterations_failed = self.total_number_of_iterations_failed + 1
        self.list_of_iterations_failed.append(self.test_config.current_iteration)
        log.info("Iterations Failed so far {}".format(self.list_of_iterations_failed))

    self.test_results_record.test_summary_record.number_of_iterations_completed = self.test_config.current_iteration
    self.test_results_record.test_summary_record.number_of_iterations_passed = self.total_number_of_iterations_passed
    self.test_results_record.test_summary_record.number_of_iterations_failed = self.total_number_of_iterations_failed
    self.test_results_record.test_summary_record.list_of_iterations_failed = self.list_of_iterations_failed
    self.test_results_record.test_summary_record.analytics_parameters = list(self.analytics_dict.keys())

    iteration_node = build_iteration_result_record(self)
    #dut_info is gathered after first iteration completed bcoz the device is provisioned and can query DUT only then.
    self.test_results_record.dut_information_record = self.dut_info
    self.test_results_record.host_information_record=self.host_info
    self.test_results_record.ci_information_record = self.ci_info
    self.test_results_record.list_of_iteration_records.insert(0,iteration_node)

    return self.test_results_record

def build_iteration_result_record(self):
    if self.iteration_test_result != TestResultEnums.TEST_RESULT_PASS:
        exeception_val = self.iteration_exception
    else:
        exeception_val = None

    iter_exec_data = IterationTCExecutionDataModel(iteration_begin_time= self.iteration_begin_time, 
                                                   iteration_end_time= self.iteration_end_time,
                                                   iteration_result=self.iteration_test_result,
                                                   exception=exeception_val)

    #update iteration_duration for the analytics dict
    self.analytics_dict.update({"iteration_duration": (self.iteration_end_time-self.iteration_begin_time).total_seconds()})

    iteration_data = IterationDatModel(iteration_tc_execution_data=iter_exec_data,
                                       iteration_tc_analytics_data= self.analytics_dict)
    
    iter_node = IterationTestResultRecordModel(
                iteration_number=self.test_config.current_iteration,
                iteration_data=iteration_data)
    
    return iter_node