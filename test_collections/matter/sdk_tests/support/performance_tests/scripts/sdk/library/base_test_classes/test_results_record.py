from mobly.records import TestResultEnums, TestResultRecord, ExceptionRecord
from enum import Enum, auto

class TestResultsEnums:
    RECORD_TEST_COMPLETED = "Test Completed"
    RECORD_TEST_IN_PROGRESS = "Test In Progress"
    RECORD_TEST_IS_ABORTED = "Test Aborted"
    RECORD_ITERATION_RESULT_PASS = 'PASS'
    RECORD_ITERATION_RESULT_FAIL = 'FAIL'
    RECORD_ITERATION_RESULT_SKIP = 'SKIP'
    RECORD_ITERATION_RESULT_ERROR = 'ERROR'
    RECORD_TEST_PASS_THRESHOLD = 95

class DUTInformationRecordEnums:
    RECORD_VENDOR_NAME  = "vendor_name"
    RECORD_PRODUCT_NAME = "product_name"
    RECORD_PRODUCT_ID   = "product_id"
    RECORD_VENDOR_ID    = "vendor_id"
    RECORD_SOFTWARE_VERSION = "software_version"
    RECORD_HARDWARE_VERSION = "hardware_version"
    RECORD_SERIAL_NUMBER = "serial_number"


