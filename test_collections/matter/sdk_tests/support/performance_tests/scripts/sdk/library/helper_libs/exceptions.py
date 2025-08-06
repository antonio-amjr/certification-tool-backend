class ReliabiltyTestError(Exception):
    """A base class for MyProject exceptions."""


class IterationError(ReliabiltyTestError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.iteration_kwarg = kwargs.get("iteration_kwarg", None)


# TODO : This error has to used fro partial execution
class TestCaseError(ReliabiltyTestError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.test_case_kwarg = kwargs.get("test_case_kwarg", None)


class TestCaseExit(ReliabiltyTestError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.test_case_kwarg = kwargs.get("test_case_kwarg")
        self.args = args

    def __str__(self):
        return f"Error: Failed to unpair the controller {self.args[0]} "


class DUTInteractionError(ReliabiltyTestError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.iteration_kwarg = kwargs.get("DUTSideError_kwarg", None)


class SshConnectionError(ReliabiltyTestError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.iteration_kwarg = kwargs.get("SshConnectionError_kwarg", None)


class SerialConnectionError(ReliabiltyTestError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.iteration_kwarg = kwargs.get("SerialConnectionError_kwarg", None)
