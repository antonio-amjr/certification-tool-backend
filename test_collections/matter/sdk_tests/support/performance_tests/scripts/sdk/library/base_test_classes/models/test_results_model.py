from pydantic import BaseModel, Field, field_validator,UUID4, model_validator
from bson import ObjectId, Binary
from typing import List, Union, Dict, Any, Optional
from pydantic_core import core_schema
import datetime
from uuid import UUID
from datetime import date

class DUTInformationRecordModel(BaseModel):
    vendor_name: str
    product_name: str
    product_id: int
    vendor_id: int
    software_version: str
    hardware_version: str
    serial_number: str = '1234'

class HostInformationRecordModel(BaseModel):
    host_name: str
    ip_address: str
    mac_address: str

class TestCaseInformationModel(BaseModel):
    test_suite_name: str
    test_case_name: str
    test_case_description: Optional[str] = None
    test_case_id: str
    test_case_class: str

class IterationTCExecutionDataModel(BaseModel):
    iteration_begin_time: Optional[datetime.datetime] = None
    iteration_end_time: Optional[datetime.datetime] = None
    iteration_result: Optional[str] = None
    exception: Optional[str] = None
    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat()  # Convert datetime to ISO format string
        }

class IterationDatModel(BaseModel):
    iteration_tc_execution_data: Optional[IterationTCExecutionDataModel]  = None
    iteration_tc_analytics_data: Optional[Dict]  = None

class IterationTestResultRecordModel(BaseModel):
    iteration_number: int
    iteration_data: Optional[IterationDatModel] = None

class ObjectIdField(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: Any
    ) -> core_schema.CoreSchema:
        object_id_schema = core_schema.chain_schema(
            [
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(cls.validate),
            ]
        )
        return core_schema.json_or_python_schema(
            json_schema=object_id_schema,
            python_schema=core_schema.union_schema(
                [core_schema.is_instance_schema(ObjectId), object_id_schema]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x)
            ),
        )

    @classmethod
    def validate(cls, value):
        if not ObjectId.is_valid(value):
            raise ValueError("Invalid id")

        return ObjectId(value)
    
class SummaryTestResultRecordModel(BaseModel):
    #test_case_info_doc_id: Optional[str] = None
    test_suite_name: Optional[str] = None
    test_case_name: Optional[str] = None
    test_case_id: Optional[str] = None
    test_case_class: Optional[str] = None
    test_case_description: Optional[str] = None
    test_case_info_doc_id: Optional[ObjectIdField] = None
    test_case_begined_at: Optional[datetime.datetime] = None
    test_case_ended_at: Optional[datetime.datetime] = None
    test_case_status: Optional[str] = None
    test_case_result: Optional[str] = None
    total_number_of_iterations: Optional[int] = None
    number_of_iterations_completed: Optional[int] = 0
    number_of_iterations_passed: Optional[int] = 0
    number_of_iterations_failed: Optional[int] = 0
    platform: Optional[str] = None
    commissioning_method: Optional[str] = None
    list_of_iterations_failed: Optional[List[int]] = None
    analytics_parameters: Optional[List[str]] = None
    mean_of_analytics: Optional[Dict[str, Union[int, float]]] = None
    

    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat()  # Convert datetime to ISO format string
        }

class CISDKGitConfigRecordModel(BaseModel):
    branch: Optional[str] = None
    sha: Optional[str] = None
    tag: Optional[str] = None

class CIInformationRecordModel(BaseModel):
    ci_job_name: Optional[str] = None
    ci_job_build_id: Optional[int] = None
    ci_ws_path: Optional[str] = None
    controller_sdk_sha: Optional[str] = None
    apps_sdk_sha: Optional[str] = None
    ci_sdk_branch: Optional[str] = None
    ci_sdk_sha: Optional[str] = None
    ci_sdk_tag: Optional[str] = None
    ci_sdk_pr: Optional[str] = None
    ci_apps_branch: Optional[str] = None
    ci_apps_sha: Optional[str] = None
    ci_apps_tag: Optional[str] = None
    ci_apps_pr: Optional[str] = None
    #sdk_git_config: Optional[CISDKGitConfigRecordModel] = None
    app_to_test: Optional[str] = None
    ci_qa_repo_branch: Optional[str] = None
    ci_qa_repo_sha: Optional[str] = None
    ci_qa_repo_tag: Optional[str] = None
    ci_qa_repo_pr: Optional[str] = None
    qa_repo_git_sha: Optional[str] = None


class TestExecutionResultsRecordModel(BaseModel):
    run_set_id: str
    test_summary_record: Optional[SummaryTestResultRecordModel] = None
    dut_info_doc_id: Optional[ObjectIdField] = None
    host_info_doc_id: Optional[ObjectIdField] = None
    ci_info_doc_id: Optional[ObjectIdField] = None
    list_of_iteration_records: list[IterationTestResultRecordModel] = []
    dut_information_record: Optional[DUTInformationRecordModel] = None
    host_information_record: Optional[HostInformationRecordModel] = None
    ci_information_record: Optional[CIInformationRecordModel] = None

