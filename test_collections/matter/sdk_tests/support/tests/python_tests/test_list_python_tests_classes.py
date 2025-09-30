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

import re
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from ...models.sdk_test_folder import SDKTestFolder
from ...python_testing.list_python_tests_classes import (
    TC_FILENAME_PATTERN,
    get_command_list,
)


@pytest.mark.parametrize(
    "filename,should_match",
    [
        # Positive test cases - should match pattern
        ("TC_ACE_1_2.py", True),
        ("TC_CNET_4_12.py", True),
        ("TC_CNET_4_99.py", True),
        ("TC_DA_1_7.py", True),
        ("TC_BINFO_2_1.py", True),
        ("TC_LVL_8_1.py", True),
        ("TC_VERYLONGCLUSTERNAME_99_99.py", True),
        ("TC_CLUSTER_1_1.py", True),
        ("TC_ACE_1_2_3.py", True),  # too many numbers - main fix
        ("TC_ACE_1_2_300.py", True),  # too many numbers - main fix
        ("TC_MCORE_FS_1_4.py", True),  # underscore in cluster name
        ("TC_ACE_1_1-custom.py", True),  # with -custom suffix at end
        ("TC_MCORE_FS_1_4-custom.py", True),  # underscore + custom suffix at end
        # Negative test cases - should NOT match pattern
        ("TC_A_0_0.py", False),  # cluster name too short (1 letter)
        ("TC_test.py", False),
        ("TC_ACE_1.py", False),
        ("TC_ACE_a_b.py", False),
        ("helper.py", False),
        ("TC_C4_1_1.py", False),
        ("TC_.py", False),
        ("test_helper.py", False),
        ("TC_ACE_1_2_extra.py", False),  # extra content after numbers
        ("TC_ACE_.py", False),  # missing second number
        ("TC_ACE_1_.py", False),  # missing second number
        ("TC_ACE__2.py", False),  # missing first number
        ("XTC_ACE_1_2.py", False),  # wrong prefix
        ("TC_ACE_1_2", False),  # missing .py extension
        ("TC_ACE_1_2.txt", False),  # wrong extension
        ("TC_1test_1_2.py", False),  # cluster name starts with number
        ("TC_ANOTHERVERYLONGCLUSTERNAME_99_99.py", False),  # cluster name > 20 chars
        ("TC_ACE_1_1-Custom.py", False),  # with -Custom suffix at end
        ("TC_ACE_1_1-CUSTOM.py", False),  # with -CUSTOM suffix at end
        ("TC_ace_1_2.py", False),  # cluster name with lowercase letters
    ],
)
def test_filename_pattern_validation(filename: str, should_match: bool) -> None:
    """Parametrized test for filename pattern validation."""
    # Use the same constant pattern as the actual implementation
    tc_pattern = re.compile(TC_FILENAME_PATTERN)

    result = tc_pattern.match(filename)
    if should_match:
        assert result is not None, f"Filename '{filename}' should match the pattern"
    else:
        assert result is None, f"Filename '{filename}' should NOT match the pattern"


def test_get_command_list_with_valid_and_invalid_files() -> None:
    """Test get_command_list with valid TC files (integration test)."""
    # This test requires the actual imports to work
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create valid test files
        valid_files = ["TC_ACE_1_2.py", "TC_CNET_4_12.py", "TC_DA_1_7.py"]

        # Create invalid test files
        invalid_files = ["TC_test.py", "helper.py", "TC_ACE_1.py"]

        # Simple test file content
        test_content = """
            import chip.clusters as Clusters
            from matter_testing_support import MatterBaseTest

            class TestClass(MatterBaseTest):
            def test_TC_example_1_1(self):
                pass
            """

        # Create all files
        for filename in valid_files + invalid_files:
            file_path = temp_path / filename
            file_path.write_text(test_content)

        test_folder = SDKTestFolder(path=temp_path, filename_pattern="*")

        # Mock the heavy processing parts
        with mock.patch("builtins.open", mock.mock_open(read_data=test_content)):
            with mock.patch("ast.parse") as mock_parse:
                with mock.patch(
                    "test_collections.matter.sdk_tests.support.python_testing."
                    "list_python_tests_classes.base_test_classes"
                ) as mock_base_classes:
                    mock_parse.return_value = mock.MagicMock()
                    mock_class = mock.MagicMock()
                    mock_class.name = "TestClass"
                    mock_base_classes.return_value = [mock_class]

                    commands = get_command_list(test_folder)

        # Should only process the 3 valid files
        assert len(commands) == 3

        # Verify only valid files are included
        file_stems = [cmd[0].split("/")[-1] for cmd in commands]
        for valid_file in valid_files:
            assert Path(valid_file).stem in file_stems

        # Verify invalid files are not included
        for invalid_file in invalid_files:
            assert Path(invalid_file).stem not in file_stems


def test_empty_folder_scenario() -> None:
    """Test pattern validation with empty folder scenario."""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            test_folder = SDKTestFolder(path=Path(temp_dir), filename_pattern="TC*")
            commands = get_command_list(test_folder)
            assert commands == []

    except ImportError:
        pytest.skip("Skipping integration test due to import dependencies")
