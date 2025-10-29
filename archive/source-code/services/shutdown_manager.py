#!/usr/bin/env python3
"""
Shutdown Manager for JARVIS
Coordinates graceful shutdown of all components with timeout-based fallback
"""
import logging
import threading
import time
from typing import Optional, Callable, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Component:
    """Represents a component that needs shutdown"""
    name: str
    shutdown_func: Callable[[], None]
    timeout: float  # seconds
    force_kill_func: Optional[Callable[[], None]] = None


class ShutdownManager:
    """
    Manages coordinated shutdown of all JARVIS components

    Features:
    - Sequential shutdown with configurable order
    - Timeout-based graceful -> forced shutdown
    - Thread-safe operation
    - Detailed shutdown logging
    - Single shutdown execution guarantee
    """

    def __init__(self, shutdown_timeout: float = 5.0):
        """
        Initialize shutdown manager

        Args:
            shutdown_timeout: Default timeout per component (seconds)
        """
        self.shutdown_timeout = shutdown_timeout
        self.components: List[Component] = []
        self._shutdown_lock = threading.Lock()
        self._shutdown_initiated = False
        self._shutdown_complete = False

        logger.info(f"ShutdownManager initialized (timeout={shutdown_timeout}s)")

    def register_component(
        self,
        name: str,
        shutdown_func: Callable[[], None],
        timeout: Optional[float] = None,
        force_kill_func: Optional[Callable[[], None]] = None
    ) -> None:
        """
        Register a component for coordinated shutdown

        Args:
            name: Component name for logging
            shutdown_func: Function to call for graceful shutdown
            timeout: Timeout in seconds (uses default if None)
            force_kill_func: Optional function to force kill if timeout exceeded
        """
        timeout = timeout or self.shutdown_timeout
        component = Component(
            name=name,
            shutdown_func=shutdown_func,
            timeout=timeout,
            force_kill_func=force_kill_func
        )
        self.components.append(component)
        logger.debug(f"Registered component: {name} (timeout={timeout}s)")

    def shutdown(self) -> bool:
        """
        Initiate coordinated shutdown of all components

        Returns:
            True if shutdown completed successfully, False if forced shutdown needed

        Shutdown order (LIFO - last registered shuts down first):
        1. UI (stop accepting input)
        2. JARVIS main loop (stop processing)
        3. Keyboard listener (cleanup subprocess)
        """
        with self._shutdown_lock:
            if self._shutdown_initiated:
                logger.warning("Shutdown already initiated, ignoring duplicate call")
                return self._shutdown_complete

            self._shutdown_initiated = True
            logger.info("=" * 60)
            logger.info("INITIATING GRACEFUL SHUTDOWN")
            logger.info("=" * 60)

        success = True

        # Shutdown components in reverse order (LIFO)
        for component in reversed(self.components):
            if not self._shutdown_component(component):
                success = False

        self._shutdown_complete = success

        if success:
            logger.info("=" * 60)
            logger.info("SHUTDOWN COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)
        else:
            logger.warning("=" * 60)
            logger.warning("SHUTDOWN COMPLETED WITH ERRORS (some components force-killed)")
            logger.warning("=" * 60)

        return success

    def _shutdown_component(self, component: Component) -> bool:
        """
        Shutdown a single component with timeout

        Args:
            component: Component to shutdown

        Returns:
            True if graceful shutdown succeeded, False if force kill needed
        """
        logger.info(f"Shutting down: {component.name} (timeout={component.timeout}s)")
        start_time = time.time()

        try:
            # Run shutdown function in a thread with timeout
            shutdown_thread = threading.Thread(
                target=component.shutdown_func,
                name=f"shutdown-{component.name}",
                daemon=True
            )
            shutdown_thread.start()
            shutdown_thread.join(timeout=component.timeout)

            if shutdown_thread.is_alive():
                # Timeout exceeded
                elapsed = time.time() - start_time
                logger.warning(
                    f"{component.name} failed to shutdown gracefully "
                    f"(timeout {component.timeout}s exceeded, took {elapsed:.1f}s)"
                )

                # Attempt force kill if available
                if component.force_kill_func:
                    logger.warning(f"Force killing {component.name}...")
                    try:
                        component.force_kill_func()
                        logger.info(f"{component.name} force killed successfully")
                        return False  # Indicate forced shutdown
                    except Exception as e:
                        logger.error(f"Failed to force kill {component.name}: {e}")
                        return False
                else:
                    logger.warning(f"No force kill function available for {component.name}")
                    return False
            else:
                elapsed = time.time() - start_time
                logger.info(f"{component.name} shutdown complete ({elapsed:.2f}s)")
                return True

        except Exception as e:
            logger.error(f"Error shutting down {component.name}: {e}", exc_info=True)

            # Attempt force kill on error
            if component.force_kill_func:
                try:
                    component.force_kill_func()
                    logger.info(f"{component.name} force killed after error")
                except Exception as e2:
                    logger.error(f"Failed to force kill {component.name} after error: {e2}")

            return False

    def is_shutdown_initiated(self) -> bool:
        """Check if shutdown has been initiated"""
        return self._shutdown_initiated

    def is_shutdown_complete(self) -> bool:
        """Check if shutdown is complete"""
        return self._shutdown_complete
