"""
Production-grade async transcription worker with timeout and health monitoring
Prevents system freezes and provides automatic recovery
"""
import threading
import queue
import time
import logging
from typing import Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionRequest:
    """Request for transcription"""
    audio: np.ndarray
    timestamp: float
    request_id: int


@dataclass
class TranscriptionResult:
    """Result from transcription"""
    request_id: int
    text: str
    latency: float
    success: bool
    error: Optional[str] = None


@dataclass
class WorkerMetrics:
    """Performance metrics for worker"""
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    timeouts: int = 0
    avg_latency: float = 0.0
    max_latency: float = 0.0
    queue_depth: int = 0
    queue_capacity: int = 0

    def update_latency(self, latency: float) -> None:
        """Update latency metrics"""
        if self.successful == 0:
            self.avg_latency = latency
        else:
            # Rolling average
            self.avg_latency = (self.avg_latency * (self.successful - 1) + latency) / self.successful
        self.max_latency = max(self.max_latency, latency)


class TranscriptionWorker:
    """
    Async transcription worker with timeout protection

    Runs transcription in background thread to prevent main loop from freezing.
    Implements timeout, health monitoring, and automatic recovery.
    """

    def __init__(
        self,
        frame_asr,
        timeout: float = 10.0,
        max_queue_size: int = 50,
        callback: Optional[Callable[[TranscriptionResult], None]] = None
    ):
        """
        Initialize transcription worker

        Args:
            frame_asr: FrameASR instance for transcription
            timeout: Maximum time to wait for transcription (seconds)
            max_queue_size: Maximum number of pending requests
            callback: Optional callback for results
        """
        self.frame_asr = frame_asr
        self.timeout = timeout
        self.callback = callback

        # Queues
        self.request_queue = queue.Queue(maxsize=max_queue_size)
        self.result_queue = queue.Queue(maxsize=max_queue_size * 2)

        # Worker thread
        self.worker_thread: Optional[threading.Thread] = None
        self.running = False

        # Metrics
        self.metrics = WorkerMetrics(queue_capacity=max_queue_size)
        self.metrics_lock = threading.Lock()

        # Request tracking
        self.next_request_id = 0
        self.current_request: Optional[TranscriptionRequest] = None
        self.current_request_start: Optional[float] = None

        # Health monitoring
        self.last_success_time = time.time()
        self.consecutive_failures = 0
        self.consecutive_timeouts = 0

        logger.info(f"TranscriptionWorker initialized: timeout={timeout}s, queue_size={max_queue_size}")

    def start(self) -> None:
        """Start the worker thread"""
        if self.running:
            logger.warning("Worker already running")
            return

        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="TranscriptionWorker")
        self.worker_thread.start()
        logger.info("TranscriptionWorker started")

    def stop(self) -> None:
        """Stop the worker thread"""
        if not self.running:
            return

        logger.info("Stopping TranscriptionWorker...")
        self.running = False

        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)
            if self.worker_thread.is_alive():
                logger.warning("Worker thread did not stop cleanly")

        logger.info("TranscriptionWorker stopped")

    def submit(self, audio: np.ndarray) -> bool:
        """
        Submit audio for transcription

        Args:
            audio: Audio data as float32 array

        Returns:
            True if accepted, False if queue is full
        """
        if not self.running:
            logger.error("Worker not running - call start() first")
            return False

        request = TranscriptionRequest(
            audio=audio,
            timestamp=time.time(),
            request_id=self.next_request_id
        )
        self.next_request_id += 1

        try:
            self.request_queue.put_nowait(request)

            with self.metrics_lock:
                self.metrics.total_requests += 1
                self.metrics.queue_depth = self.request_queue.qsize()

            # Log queue utilization warnings
            utilization = self.request_queue.qsize() / self.metrics.queue_capacity
            if utilization > 0.75:
                logger.critical(
                    f"Transcription queue critical: {self.request_queue.qsize()}/{self.metrics.queue_capacity} "
                    f"({utilization*100:.0f}% full) - System degraded"
                )
            elif utilization > 0.50:
                logger.warning(
                    f"Transcription queue high: {self.request_queue.qsize()}/{self.metrics.queue_capacity} "
                    f"({utilization*100:.0f}% full)"
                )

            return True

        except queue.Full:
            logger.error("Transcription queue full - dropping request")
            return False

    def get_result(self, timeout: float = 0.01) -> Optional[TranscriptionResult]:
        """
        Get next transcription result

        Args:
            timeout: Timeout in seconds

        Returns:
            TranscriptionResult or None
        """
        try:
            result = self.result_queue.get(timeout=timeout)

            # Call callback if registered
            if self.callback:
                try:
                    self.callback(result)
                except Exception as e:
                    logger.error(f"Error in result callback: {e}")

            return result

        except queue.Empty:
            return None

    def get_metrics(self) -> WorkerMetrics:
        """Get current performance metrics (thread-safe copy)"""
        with self.metrics_lock:
            metrics = WorkerMetrics(
                total_requests=self.metrics.total_requests,
                successful=self.metrics.successful,
                failed=self.metrics.failed,
                timeouts=self.metrics.timeouts,
                avg_latency=self.metrics.avg_latency,
                max_latency=self.metrics.max_latency,
                queue_depth=self.request_queue.qsize(),
                queue_capacity=self.metrics.queue_capacity
            )
        return metrics

    def is_healthy(self) -> bool:
        """
        Check if worker is healthy

        Returns:
            True if healthy, False if degraded/failing
        """
        # Check consecutive failures
        if self.consecutive_failures > 5:
            return False

        # Check consecutive timeouts
        if self.consecutive_timeouts > 3:
            return False

        # Check if we've had any success recently (last 30 seconds)
        time_since_success = time.time() - self.last_success_time
        if time_since_success > 30.0 and self.metrics.total_requests > 0:
            return False

        return True

    def _worker_loop(self) -> None:
        """Main worker loop - runs in background thread"""
        logger.info("Worker loop started")

        while self.running:
            try:
                # Get next request with timeout to allow clean shutdown
                try:
                    request = self.request_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Update current request (for watchdog)
                self.current_request = request
                self.current_request_start = time.time()

                # Transcribe with timeout protection
                result = self._transcribe_with_timeout(request)

                # Clear current request
                self.current_request = None
                self.current_request_start = None

                # Update metrics
                with self.metrics_lock:
                    if result.success:
                        self.metrics.successful += 1
                        self.metrics.update_latency(result.latency)
                        self.last_success_time = time.time()
                        self.consecutive_failures = 0
                        self.consecutive_timeouts = 0
                    else:
                        self.metrics.failed += 1
                        self.consecutive_failures += 1
                        if "timeout" in (result.error or "").lower():
                            self.metrics.timeouts += 1
                            self.consecutive_timeouts += 1

                    self.metrics.queue_depth = self.request_queue.qsize()

                # Send result
                try:
                    self.result_queue.put_nowait(result)
                except queue.Full:
                    logger.error("Result queue full - dropping result")

                # Log performance warnings
                if result.success and result.latency > 5.0:
                    logger.warning(f"Slow transcription: {result.latency:.1f}s (timeout={self.timeout}s)")
                elif result.success and result.latency > 2.0:
                    logger.info(f"Transcription latency: {result.latency:.1f}s")

            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)
                time.sleep(0.1)  # Prevent tight error loop

        logger.info("Worker loop exited")

    def _transcribe_with_timeout(self, request: TranscriptionRequest) -> TranscriptionResult:
        """
        Transcribe with timeout protection

        Uses a separate thread to run transcription and kills it if it takes too long.

        Args:
            request: TranscriptionRequest

        Returns:
            TranscriptionResult
        """
        result_container = []
        error_container = []

        def _do_transcribe():
            """Inner function that runs in timeout thread"""
            try:
                start_time = time.time()
                text = self.frame_asr.transcribe_chunk(request.audio)
                latency = time.time() - start_time
                result_container.append((text, latency))
            except Exception as e:
                error_container.append(e)

        # Start transcription in separate thread
        transcribe_thread = threading.Thread(target=_do_transcribe, daemon=True)
        start_time = time.time()
        transcribe_thread.start()

        # Wait with timeout
        transcribe_thread.join(timeout=self.timeout)

        # Check result
        if transcribe_thread.is_alive():
            # Timeout - thread is still running
            logger.error(
                f"Transcription timeout after {self.timeout}s "
                f"(request_id={request.request_id}, consecutive_timeouts={self.consecutive_timeouts + 1})"
            )
            return TranscriptionResult(
                request_id=request.request_id,
                text="",
                latency=self.timeout,
                success=False,
                error=f"Timeout after {self.timeout}s"
            )

        # Check for errors
        if error_container:
            error = error_container[0]
            logger.error(f"Transcription error: {error}", exc_info=True)
            return TranscriptionResult(
                request_id=request.request_id,
                text="",
                latency=time.time() - start_time,
                success=False,
                error=str(error)
            )

        # Success
        if result_container:
            text, latency = result_container[0]
            return TranscriptionResult(
                request_id=request.request_id,
                text=text,
                latency=latency,
                success=True
            )

        # Should not reach here
        logger.error("Transcription completed but no result")
        return TranscriptionResult(
            request_id=request.request_id,
            text="",
            latency=time.time() - start_time,
            success=False,
            error="No result returned"
        )
