import pymongo.errors
from .test_observer import Observable, Observer
from mobly import signals
from matter_qa.library.helper_libs.logger import qa_logger

import matter_qa.library.base_test_classes.test_results_record as tr
import logging
import pymongo
from pymongo import MongoClient
from bson import ObjectId
from .models.test_results_model import *
import copy
import asyncio
from typing import Optional
from pymongo import ASCENDING

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("db_observer")
log.propagate = True

class TestResultDBObserver(Observer):
    def __init__(self, mongodb_server_config):
        self._connect_to_mongodb(mongodb_server_config)
        self._create_db_collection()
        self._init_attributes()
        self._create_unique_indices(
            [{self.dut_info_collection: "serial_number"}, {self.host_info_collection: "mac_address"},
            {self.test_case_info_collection: "test_case_id"}, {self.test_execution_results_collection: "run_set_id"},
            {self.ci_info_collection: [("ci_job_name", ASCENDING), ("ci_job_build_id", ASCENDING)]}])
        
        # Queue for background upload tasks
        #self.upload_queue = asyncio.Queue()

        # Start background task to upload data asynchronously
        #asyncio.create_task(self._process_upload_queue())

    def _connect_to_mongodb(self, mongodb_server_config):
        if hasattr(mongodb_server_config, "username") and hasattr(mongodb_server_config, "password"):
            if mongodb_server_config.username and mongodb_server_config.password:
                self.client = MongoClient('mongodb://{}:{}@{}/'.format(mongodb_server_config.username,
                                                                    mongodb_server_config.password,
                                                                    mongodb_server_config.server_url))
            else:
                self.client = MongoClient('mongodb://{}/'.format(mongodb_server_config.server_url))
                log.info("connected to the mongodb server")
        else:
            log.error("Could not establish connection with mongodb server, \
                      pls check server url, username and password provided in the config")
            raise Exception("Failing Test, Could not establish Connection to MongoDB server {}".format(mongodb_server_config.server_url))

    def _create_db_collection(self):
        self.db = self.client['qa_test_results_database']
        self.dut_info_collection = self.db["dut_info_collection"]
        self.host_info_collection = self.db["host_info_collection"]
        self.test_case_info_collection = self.db["test_case_info_collection"]
        self.test_execution_results_collection = self.db['test_execution_results_collection']
        self.ci_info_collection = self.db["ci_info_collection"]
        log.info("created db and dut_info_collection,dut_info_collection,dut_info_collection,\
                  test_execution_results_collection, ci_info_collection")

    def _init_attributes(self):
        self.run_set_id = None
        self.dut_doc_id = None
        self.host_info_doc_id = None
        self.test_case_info_doc_id = None
        self.test_execution_results_doc_id = None
        self.ci_info_doc_id = None

    def _create_unique_indices(self, list_of_collections):
        for item in list_of_collections:
            self._create_unique_index(list(item.keys())[0], list(item.values())[0])

    def _create_unique_index(self, collection, index_keys):
        try:
            collection.create_index(index_keys, unique=True)
        except pymongo.errors.OperationFailure as e:
            if 'already exists' not in str(e):
                # TODO handle this exit properly.
                raise signals.TestAbortAll(f"Failed to create a unique index with error:{e}")

    def find_or_update_document(self, collection, query, document, update_doc=False):
        # Search for the document
        existing_document = collection.find_one(query)
        if existing_document:
            if update_doc:
                collection.update_one(query, {'$set': document})
            return existing_document['_id']
        else:
            # Document not found, insert a new one
            result = collection.insert_one(document)
            return result.inserted_id

    def get_document_from_collection(self, collection, query):
        document = collection.find_one(query)
        if document:
            return document
    
    async def _process_upload_queue(self):
        while True:
            # Wait until there's a task in the queue
            record = await self.upload_queue.get()
            if record is None:
                break  # Exit the loop if the termination signal is received

            try:
                await self._upload_to_mongodb(record)
            except Exception as e:
                log.error(f"Failed to upload record: {e}")
            finally:
                self.upload_queue.task_done()

    def dispatch(self, record):
        test_execution_results_record = copy.deepcopy(record)
        # find if the test_case_info is already in the DB
        if self.test_case_info_doc_id is None:
            tc_document = test_execution_results_record.test_summary_record.model_dump(include={'test_suite_name': True,
                                                                                                'test_case_name': True,
                                                                                                'test_case_id': True,
                                                                                                'test_case_class': True,
                                                                                                'test_case_description': True})

            self.test_case_info_doc_id = self.find_or_update_document(collection=self.test_case_info_collection,
                                                                      query={
                                                                          'test_case_id': tc_document["test_case_id"],
                                                                          'test_suite_name': tc_document[
                                                                              "test_suite_name"]}, document=tc_document)

            log.info("test case info record created and inserted in the collection")

            # we dont need to insert test_suite_name, test_case_name, id and class info in DB, instead we will have doc_id of test_summary
            text_exec_record_document = test_execution_results_record.model_dump(exclude={'test_summary_record':
                                                                                              {'test_suite_name': True,
                                                                                               'test_case_name': True,
                                                                                               'test_case_id': True,
                                                                                               'test_case_class': True,
                                                                                               'test_case_description': True
                                                                                               },
                                                                                          'dut_information_record': True,
                                                                                          'host_information_record': True,
                                                                                          'ci_information_record': True
                                                                                          })
            # update the test_case_info_doc_id into the summary document , dont assign it to var as it returns None
            text_exec_record_document.update(
                {"test_summary_record": {"test_case_info_doc_id": self.test_case_info_doc_id}})
            self.run_set_id = test_execution_results_record.run_set_id
            self.test_execution_results_doc_id = self.find_or_update_document(
                collection=self.test_execution_results_collection,
                query={'run_set_uuid': self.run_set_id}, document=text_exec_record_document)
            log.info("test_execution_results record created at the start of the test")

        if self.dut_doc_id is None:
            if test_execution_results_record.dut_information_record is not None:
                # read the data sent by the observable
                dut_info_doc = test_execution_results_record.dut_information_record.model_dump()
                self.dut_doc_id = self.find_or_update_document(collection=self.dut_info_collection,
                                                               query={
                                                                   'vendor_name': dut_info_doc["vendor_name"],
                                                                   'product_name': dut_info_doc["product_name"],
                                                                   'product_id': dut_info_doc["product_id"],
                                                                   'vendor_id': dut_info_doc["vendor_id"],
                                                                   "software_version": dut_info_doc["software_version"],
                                                                   "hardware_version": dut_info_doc["hardware_version"],
                                                                   'serial_number': dut_info_doc["serial_number"]
                                                               },
                                                               document=dut_info_doc)
                test_execution_results_record.dut_info_doc_id = self.dut_doc_id
                log.info("dut information record created in dut_info_collection")

        if self.host_info_doc_id is None:
            if test_execution_results_record.host_information_record is not None:
                host_info_doc = test_execution_results_record.host_information_record.model_dump()
                self.host_info_doc_id = self.find_or_update_document(collection=self.host_info_collection,
                                                                     query={
                                                                         'mac_address': host_info_doc["mac_address"]},
                                                                     document=host_info_doc)
                test_execution_results_record.host_info_doc_id = self.host_info_doc_id
                log.info("host information record created in host_info_collection")
        
        if self.ci_info_doc_id is None:
            if test_execution_results_record.ci_information_record is not None:
                ci_info_doc = test_execution_results_record.ci_information_record.model_dump()
                self.ci_info_doc_id = self.find_or_update_document(collection=self.ci_info_collection,
                                                                     query={
                                                                        'ci_job_name': ci_info_doc["ci_job_name"],
                                                                        'ci_job_build_id':  ci_info_doc["ci_job_build_id"],
                                                                         },
                                                                     document=ci_info_doc)
                test_execution_results_record.ci_info_doc_id = self.ci_info_doc_id
                log.info("ci information record created in ci_info_collection")

        if test_execution_results_record.list_of_iteration_records != []:
            iteration_test_result_node = test_execution_results_record.list_of_iteration_records[0]
            iteration_number = iteration_test_result_node.iteration_number
            # fetch the document and update with latest details of summary, dut, list of iterations
            test_execution_result_document = self.get_document_from_collection(self.test_execution_results_collection,
                                                                               query={'run_set_id': self.run_set_id})

            test_execution_result_object = TestExecutionResultsRecordModel(**test_execution_result_document)

            if len(test_execution_result_object.list_of_iteration_records) < iteration_number:
                test_execution_result_object.list_of_iteration_records.append(iteration_test_result_node)
            else:
                test_execution_result_object.list_of_iteration_records[
                    iteration_number - 1] = iteration_test_result_node

            test_execution_result_object.dut_info_doc_id = self.dut_doc_id
            test_execution_result_object.host_info_doc_id = self.host_info_doc_id
            test_execution_result_object.ci_info_doc_id = self.ci_info_doc_id
            # get the summary record, strip out TC details.
            summary_rec = test_execution_results_record.test_summary_record
            del summary_rec.test_suite_name, summary_rec.test_case_name, summary_rec.test_case_id, summary_rec.test_case_description, summary_rec.test_case_class
            summary_rec.test_case_info_doc_id = self.test_case_info_doc_id
            test_execution_result_object.test_summary_record = summary_rec

            # in DB we store only doc ID , so we are excluding the record inforamtion
            document = test_execution_result_object.model_dump(exclude={'dut_information_record': True,
                                                                        'host_information_record': True,
                                                                        'ci_information_record': True})

            self.find_or_update_document(self.test_execution_results_collection, query={'run_set_id': self.run_set_id},
                                         document=document, update_doc=True)
            log.info("finished updating the test_execution_result in the test_execution_results_collection")
    
    


