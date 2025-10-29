"""
Retry utilities for error recovery
Implements exponential backoff with configurable parameters
"""
import time
import logging
from typing import Callable, TypeVar, Optional, Type
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryExhausted(Exception):
    """Raised when all retry attempts have been exhausted"""
    pass


def exponential_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
) -> T:
    """
    Execute function with exponential backoff retry logic

    Args:
        func: Function to execute
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        exceptions: Tuple of exceptions to catch and retry
        on_retry: Optional callback function called on each retry

    Returns:
        Result from successful function execution

    Raises:
        RetryExhausted: If all retries are exhausted
        Exception: If a non-retryable exception occurs
    """
    delay = initial_delay

    for attempt in range(max_retries + 1):
        try:
            return func()
        except exceptions as e:
            if attempt >= max_retries:
                logger.error(
                    f"All {max_retries} retry attempts exhausted for {func.__name__}: {e}"
                )
                raise RetryExhausted(
                    f"Failed after {max_retries} retries: {e}"
                ) from e

            # Calculate next delay with exponential backoff
            wait_time = min(delay, max_delay)
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                f"Retrying in {wait_time:.1f}s..."
            )

            # Call retry callback if provided
            if on_retry:
                try:
                    on_retry(e, attempt + 1)
                except Exception as callback_error:
                    logger.error(f"Error in retry callback: {callback_error}")

            time.sleep(wait_time)
            delay *= exponential_base


def retry_on_exception(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for automatic retry with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        exceptions: Tuple of exceptions to catch and retry

    Example:
        @retry_on_exception(max_retries=3, initial_delay=1.0)
        def unreliable_function():
            # ... code that might fail ...
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return exponential_backoff(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                initial_delay=initial_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                exceptions=exceptions
            )
        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern for failing components

    States:
    - CLOSED: Normal operation, allow requests
    - OPEN: Too many failures, reject requests
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        """
        Initialize circuit breaker

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before trying again (seconds)
            expected_exception: Exception type to track
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

        logger.info(
            f"CircuitBreaker initialized (threshold={failure_threshold}, "
            f"timeout={recovery_timeout}s)"
        )

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function through circuit breaker

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result from function execution

        Raises:
            Exception: If circuit is OPEN or function fails
        """
        if self.state == "OPEN":
            # Check if recovery timeout has passed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                logger.info("Circuit breaker: Attempting recovery (HALF_OPEN)")
                self.state = "HALF_OPEN"
            else:
                raise Exception(
                    f"Circuit breaker OPEN: Service unavailable "
                    f"(too many failures, retry after {self.recovery_timeout}s)"
                )

        try:
            result = func(*args, **kwargs)

            # Success - reset failure count
            if self.state == "HALF_OPEN":
                logger.info("Circuit breaker: Service recovered (CLOSED)")
                self.state = "CLOSED"
                self.failure_count = 0

            return result

        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            logger.warning(
                f"Circuit breaker: Failure {self.failure_count}/{self.failure_threshold}"
            )

            if self.failure_count >= self.failure_threshold:
                logger.error(
                    f"Circuit breaker: OPEN (threshold reached: {self.failure_threshold} failures)"
                )
                self.state = "OPEN"

            raise

    def reset(self) -> None:
        """Manually reset circuit breaker"""
        logger.info("Circuit breaker: Manual reset")
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_failure_time = None

    def get_state(self) -> dict:
        """Get circuit breaker state"""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time
        }
