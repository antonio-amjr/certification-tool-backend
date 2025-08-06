from enum import Enum

class OperationalTimingEnums(Enum):
    """
    Generic timing constants (in seconds) used for operational workflows
    that require periodic checks and a maximum allowable wait duration.

    Attributes:
        RETRY_INTERVAL:
            The interval, in seconds, between successive checks or retries.
            For example, this defines how frequently an operation polls
            for completion or retries a pending task.
        
        OVERALL_TIMEOUT:
            The maximum total duration, in seconds, to wait for an operation
            to complete before considering it to have failed or timed out.

    Example:
        Usage in an operation that polls for a condition to be met:

        >>> import time
        >>> start_time = time.time()
        >>> while time.time() - start_time < OperationalTimingEnums.OVERALL_TIMEOUT.value:
        ...     if some_condition():
        ...         print("Operation completed successfully.")
        ...         break
        ...     time.sleep(OperationalTimingEnums.RETRY_INTERVAL.value)
        ... else:
        ...     print("Operation timed out.")
    """

    RETRY_INTERVAL = 1
    OVERALL_TIMEOUT = 50