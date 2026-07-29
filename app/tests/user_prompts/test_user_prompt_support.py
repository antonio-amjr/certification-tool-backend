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
from unittest import mock
from unittest.mock import MagicMock

import pytest

from app.user_prompt_support import user_prompt_manager
from app.user_prompt_support.user_prompt_support import (
    UserPromptError,
    UserPromptSupport,
    resolve_user_prompt_timeout,
)


@pytest.mark.asyncio
async def test_send_prompt_request_no_response() -> None:
    """
    Validate that send_prompt_request() raises an exception upon no response.
    """
    prompt_support = UserPromptSupport()

    with mock.patch.object(
        user_prompt_manager.user_prompt_manager,
        "send_prompt_request",
        return_value=None,
    ) as send_prompt_request:
        with pytest.raises(UserPromptError):
            await prompt_support.send_prompt_request(prompt_request=mock.MagicMock())
            send_prompt_request.assert_called_once()


def test_resolve_user_prompt_timeout_uses_configured_value() -> None:
    config = {"test_harness_config": {"user_prompt_timeout_s": 300}}
    assert resolve_user_prompt_timeout(config, default=60) == 300


@pytest.mark.parametrize(
    "config",
    [
        None,
        {},
        {"test_harness_config": {}},
        {"test_harness_config": {"user_prompt_timeout_s": None}},
        {"test_harness_config": {"user_prompt_timeout_s": 0}},
        {"test_harness_config": {"user_prompt_timeout_s": -5}},
        {"test_harness_config": {"user_prompt_timeout_s": "300"}},
        {"test_harness_config": "not_a_dict"},
    ],
)
def test_resolve_user_prompt_timeout_falls_back_to_default(config: object) -> None:
    assert resolve_user_prompt_timeout(config, default=60) == 60  # type: ignore


def test_resolve_prompt_timeout_reads_test_case_config() -> None:
    """When mixed into a TestCase-like object with a `.config` property, the
    configured test_harness_config.user_prompt_timeout_s should be used."""

    class FakeTestCase(UserPromptSupport):
        config = {"test_harness_config": {"user_prompt_timeout_s": 300}}

    assert FakeTestCase().resolve_prompt_timeout(default=60) == 300


def test_resolve_prompt_timeout_falls_back_without_config() -> None:
    """When there is no `.config` and no `.test_step_execution`, the default
    is used."""
    assert UserPromptSupport().resolve_prompt_timeout(default=60) == 60


def test_resolve_prompt_timeout_reads_test_step_execution_chain() -> None:
    """When mixed into a TestStep-like object (no `.config`), the timeout is
    resolved by walking test_step_execution -> ... -> project.config."""

    class FakeTestStep(UserPromptSupport):
        pass

    step = FakeTestStep()
    test_run_execution = MagicMock()
    test_run_execution.execution_config = None
    test_run_execution.project.config = {
        "test_harness_config": {"user_prompt_timeout_s": 120}
    }

    test_step_execution = MagicMock()
    chain = test_step_execution.test_case_execution.test_suite_execution
    chain.test_run_execution = test_run_execution
    step.test_step_execution = test_step_execution

    assert step.resolve_prompt_timeout(default=60) == 120


def test_resolve_prompt_timeout_prefers_execution_config_override() -> None:
    """execution_config (temporary CLI/API override) takes precedence over
    the persistent project.config, matching TestCase.config's behavior."""

    class FakeTestStep(UserPromptSupport):
        pass

    step = FakeTestStep()
    test_run_execution = MagicMock()
    test_run_execution.execution_config = {
        "test_harness_config": {"user_prompt_timeout_s": 999}
    }
    test_run_execution.project.config = {
        "test_harness_config": {"user_prompt_timeout_s": 120}
    }

    test_step_execution = MagicMock()
    chain = test_step_execution.test_case_execution.test_suite_execution
    chain.test_run_execution = test_run_execution
    step.test_step_execution = test_step_execution

    assert step.resolve_prompt_timeout(default=60) == 999

