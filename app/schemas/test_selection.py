#
# Copyright (c) 2023 Project CHIP Authors
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
"""Schemas for test selection structures."""

from typing import Dict

from pydantic import BaseModel


class SelectedTests(BaseModel):
    """
    Schema for selected tests structure.

    This represents the nested dictionary structure for test selection:
    - Outer dict: Test collection name -> Test suites
    - Middle dict: Test suite public_id -> Test cases
    - Inner dict: Test case public_id -> iteration count

    Example:
        {
            "collection_name": {
                "suite_id": {
                    "case_id": 1
                }
            }
        }
    """

    __root__: Dict[str, Dict[str, Dict[str, int]]]

    class Config:
        schema_extra = {"example": {"collection_name": {"suite_id": {"case_id": 1}}}}
