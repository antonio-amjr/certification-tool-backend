#
# Copyright (c) 2026 Project CHIP Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Schemas for file upload operations and request bodies."""

from typing import Any

from fastapi import UploadFile
from pydantic import BaseModel, Field

from app.schemas.test_run_execution import TestRunExecutionCreate
from app.schemas.test_selection import SelectedTests


class ProjectFileUpload(BaseModel):
    """Schema for project file uploads (PICS or DMP test skip).

    Example:
        {
            "file": <binary file data>
        }
    """

    file: UploadFile = Field(
        ..., description="PICS file or dmp-test-skip.xml file to upload"
    )

    class Config:
        arbitrary_types_allowed = True
        schema_extra = {"example": {"file": "pics_file.txt"}}


class ProjectConfigImport(BaseModel):
    """Schema for project configuration import.

    Example:
        {
            "import_file": <binary JSON file data>
        }
    """

    import_file: UploadFile = Field(
        ..., description="Project configuration JSON file to import"
    )

    class Config:
        arbitrary_types_allowed = True
        schema_extra = {"example": {"import_file": "project-config.json"}}


class TestRunFileUpload(BaseModel):
    """Schema for test run file uploads.

    Example:
        {
            "file": <binary file data>
        }
    """

    file: UploadFile = Field(..., description="File to upload for the current test run")

    class Config:
        arbitrary_types_allowed = True
        schema_extra = {"example": {"file": "test-data.bin"}}


class TestRunExecutionImport(BaseModel):
    """Schema for test run execution import.

    Example:
        {
            "import_file": <binary JSON file data>
        }
    """

    import_file: UploadFile = Field(
        ..., description="Test run execution JSON file to import"
    )

    class Config:
        arbitrary_types_allowed = True
        schema_extra = {"example": {"import_file": "test-run-export.json"}}


class TestRunExecutionCreateRequest(BaseModel):
    """Schema for creating a test run execution with selected tests.

    This schema wraps the parameters for creating a test run execution,
    replacing the auto-generated Body_* schema.

    Example:
        {
            "test_run_execution_in": {...},
            "selected_tests": {...}
        }
    """

    test_run_execution_in: TestRunExecutionCreate = Field(
        ..., description="Test run execution data"
    )
    selected_tests: SelectedTests = Field(..., description="Selected tests to run")

    class Config:
        schema_extra = {
            "example": {
                "test_run_execution_in": {
                    "title": "Test Run 1",
                    "description": "Sample test run",
                    "project_id": 1,
                },
                "selected_tests": {},
            }
        }


class CLITestRunExecutionCreateRequest(BaseModel):
    """Schema for creating a CLI test run execution with configuration.

    This schema wraps the parameters for creating a CLI test run execution,
    replacing the auto-generated Body_* schema.

    Example:
        {
            "test_run_execution_in": {...},
            "selected_tests": {...},
            "config": {...},
            "execution_config": {...},
            "pics": {...}
        }
    """

    test_run_execution_in: TestRunExecutionCreate = Field(
        ..., description="Test run execution data"
    )
    selected_tests: SelectedTests = Field(..., description="Selected tests to run")
    config: dict[str, Any] | None = Field(
        None, description="Configuration parameters that update project (persists)"
    )
    execution_config: dict[str, Any] | None = Field(
        None, description="Execution-specific config override (temporary)"
    )
    pics: dict[str, Any] = Field(default_factory=dict, description="PICS configuration")

    class Config:
        schema_extra = {
            "example": {
                "test_run_execution_in": {
                    "title": "CLI Test Run",
                    "description": "Test run from CLI",
                    "project_id": 1,
                },
                "selected_tests": {},
                "config": {},
                "execution_config": {},
                "pics": {},
            }
        }
