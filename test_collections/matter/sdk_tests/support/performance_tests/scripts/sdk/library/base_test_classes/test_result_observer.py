from .test_observer import Observable,Observer
from matter_qa.library.helper_libs.logger import qa_logger
import matter_qa.library.base_test_classes.test_results_record as tr
import json
import os
import logging
import sys
import datetime
import copy
import time
from .models.test_results_model import *
from mobly import signals
log = logging.getLogger("result_observer")
log.propagate = True
class TestResultObserver(Observer):
    def __init__(self, file_tc_summary):
        self.file_tc_summary = file_tc_summary

    def custom_json_serializer(self,obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        
    def dispatch(self, record):
        if record is not None:
            test_execution_results_record = copy.deepcopy(record)
            
            # if file doesnt exist
            if not os.path.exists(self.file_tc_summary):
                # File doesn't exist, create it and write default data
                with open(self.file_tc_summary, 'w') as file:
                    json_data = test_execution_results_record.model_dump(exclude={'dut_info_doc_id':True,
                                                                            'host_info_doc_id':True,
                                                                            'ci_info_doc_id':True,
                                                                            'test_summary_record':{
                                                                                'test_case_info_doc_id': True
                                                                            }})
                    json.dump(json_data, file, indent=4, default=self.custom_json_serializer)
                    log.info("{} file created".format(self.file_tc_summary))
            else:
                with open(self.file_tc_summary, 'r') as file:
                    try:
                        json_data = json.load(file)
                    except Exception as e:
                        logging.info(f'Error loading JSON file: {e}')
                        raise signals.TestAbortAll(f"Error loading JSON file: {e}")
                    test_execution_result_object = TestExecutionResultsRecordModel(**json_data)
                    test_execution_result_object.test_summary_record = test_execution_results_record.test_summary_record
                    # we are not using these two records anywhere
                    test_execution_result_object.dut_information_record = test_execution_results_record.dut_information_record
                    test_execution_result_object.host_information_record = test_execution_results_record.host_information_record
                    test_execution_result_object.ci_information_record = test_execution_results_record.ci_information_record

                    
                    list_of_iterations_in_file = test_execution_result_object.list_of_iteration_records
                    list_of_iterations_in_record_recived = test_execution_results_record.list_of_iteration_records
                    if list_of_iterations_in_record_recived != []:
                        # append the test iteration result to the list of existing iterations.
                        iteration_test_result_node = list_of_iterations_in_record_recived[0]
                        iteration_number = iteration_test_result_node.iteration_number

                        if len(list_of_iterations_in_file) < iteration_number :
                            list_of_iterations_in_file.append(iteration_test_result_node)
                        else:
                            list_of_iterations_in_file[iteration_number-1] = iteration_test_result_node


                json_data = test_execution_result_object.model_dump(exclude={'dut_info_doc_id':True,
                                                                            'host_info_doc_id':True,
                                                                            'ci_info_doc_id':True,
                                                                            'test_summary_record':{
                                                                                'test_case_info_doc_id': True
                                                                            }})

                with open(self.file_tc_summary, 'w') as file_write:
                    json.dump(json_data, file_write, indent=4, default=self.custom_json_serializer)
                log.info("{} file updated with the test results information".format(self.file_tc_summary))