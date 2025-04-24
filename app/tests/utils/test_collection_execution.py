#
# Copyright (c) 2025 Project CHIP Authors
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

from datetime import datetime
from typing import Any

from faker import Faker

from app.models.test_enums import TestStateEnum
from app.tests.utils.utils import random_lower_string

fake = Faker()


def create_random_test_collection_execution_dict(
    name: str | None = None,
    state: TestStateEnum | None = None,
    execution_index: int | None = None,
    mandatory: bool | None = None,
    errors: list[str] | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    test_run_execution_id: int | None = None,
    test_collection_metadata_id: int | None = None,
) -> dict[str, Any]:
    collection_execution_dict: dict[str, Any] = {}

    # Name is not optional
    if name is None:
        name = random_lower_string()
    collection_execution_dict["name"] = name

    # Execution_index is not optional
    if execution_index is None:
        execution_index = fake.random_int(max=99)
    collection_execution_dict["execution_index"] = execution_index

    # The test_collection_metadata_id is not optional
    if test_collection_metadata_id is None:
        test_collection_metadata_id = fake.random_int(max=99)
    collection_execution_dict[
        "test_collection_metadata_id"
    ] = test_collection_metadata_id

    # The test_run_execution_id is not optional
    if test_run_execution_id is None:
        test_run_execution_id = fake.random_int(max=99)
    collection_execution_dict["test_run_execution_id"] = test_run_execution_id

    # State has default value, include if present
    if state is not None:
        collection_execution_dict["state"] = state

    # Mandatory has default value, include if present
    if mandatory is not None:
        collection_execution_dict["mandatory"] = mandatory

    # Errors has default value, include if present
    if errors is not None:
        collection_execution_dict["errors"] = errors

    # Started At is optional, include if present
    if started_at is not None:
        collection_execution_dict["started_at"] = started_at

    # Completed At is optional, include if present
    if completed_at is not None:
        collection_execution_dict["completed_at"] = completed_at

    return collection_execution_dict
