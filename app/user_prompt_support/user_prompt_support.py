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
from typing import Optional

from .constants import UserResponseStatusEnum
from .prompt_request import PromptRequest
from .prompt_response import PromptResponse
from .user_prompt_manager import user_prompt_manager


class UserPromptError(Exception):
    pass


class InvalidPromptInput(Exception):
    pass


def resolve_user_prompt_timeout(config: Optional[dict], default: int) -> int:
    """Resolve the user-prompt timeout (seconds) from a project/execution
    config dict, falling back to `default` if not configured."""
    if not config:
        return default

    test_harness_config = config.get("test_harness_config")
    if not isinstance(test_harness_config, dict):
        return default

    timeout = test_harness_config.get("user_prompt_timeout_s")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        return default

    return timeout


class UserPromptSupport(object):
    def resolve_prompt_timeout(self, default: int) -> int:
        """Resolve the configured user-prompt timeout for this test case/step,
        falling back to `default` if no override is configured.

        Works whether `self` is a TestCase (has a `.config` property) or a
        TestStep (reaches its config via `.test_step_execution`).
        """
        config = getattr(self, "config", None)

        if config is None:
            test_step_execution = getattr(self, "test_step_execution", None)
            if test_step_execution is not None:
                test_run_execution = (
                    test_step_execution.test_case_execution
                    .test_suite_execution.test_run_execution
                )
                config = test_run_execution.execution_config
                if config is None:
                    config = test_run_execution.project.config

        return resolve_user_prompt_timeout(config, default)

    async def send_prompt_request(
        self, prompt_request: PromptRequest
    ) -> PromptResponse:
        response = await user_prompt_manager.send_prompt_request(prompt_request)

        if response is None:
            raise UserPromptError("No prompt response returned")
        return response

    async def invoke_prompt_and_get_str_response(
        self, prompt_request: PromptRequest
    ) -> str:
        prompt_response = await self.send_prompt_request(prompt_request=prompt_request)
        if (
            prompt_response.status_code != UserResponseStatusEnum.OKAY
            or not prompt_response.response_str
        ):
            raise InvalidPromptInput(
                f"""Expected input type str but received {type(prompt_response)}.
                Received user response {prompt_response}."""
            )
        return prompt_response.response_str

    async def invoke_prompt_and_get_int_response(
        self, prompt_request: PromptRequest
    ) -> int:
        prompt_response = await self.send_prompt_request(prompt_request=prompt_request)
        if (
            prompt_response.status_code != UserResponseStatusEnum.OKAY
            or not isinstance(prompt_response.response, int)
            or isinstance(prompt_response.response, bool)
        ):
            raise InvalidPromptInput(
                f"""Expected input type int but received {type(prompt_response)}.
                Received user response {prompt_response}."""
            )
        return prompt_response.response
