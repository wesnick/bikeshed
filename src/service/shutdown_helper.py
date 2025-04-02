import asyncio
from typing import List
import signal
import sys
import time
from src.service.logging import logger


class ShutdownManager:
    """
    Manages graceful shutdown of the application.

    This class helps coordinate the shutdown of various components,
    especially those with async generators that need proper cleanup.
    """

    def __init__(self):
        self._shutdown_tasks: List[asyncio.Task] = []
        self._cleanup_hooks: List[callable] = []
        self._is_shutting_down = False
        self._shutdown_event = asyncio.Event()

    def register_cleanup_hook(self, hook: callable):
        """Register a function to be called during shutdown"""
        self._cleanup_hooks.append(hook)

    async def trigger_shutdown(self, reason: str = "Shutdown requested"):
        """Trigger the shutdown process"""
        if self._is_shutting_down:
            return

        self._is_shutting_down = True
        logger.warning(f"Initiating graceful shutdown: {reason}")

        # Set the shutdown event
        self._shutdown_event.set()

        # Run all cleanup hooks
        for hook in self._cleanup_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()
            except Exception as e:
                logger.error(f"Error in cleanup hook: {e}")

        # Wait a moment for cleanup to complete
        await asyncio.sleep(0.5)

    def install_signal_handlers(self):
        """Install signal handlers for graceful shutdown"""
        # Store original handlers
        original_term_handler = signal.getsignal(signal.SIGTERM)
        original_int_handler = signal.getsignal(signal.SIGINT)

        def signal_handler(sig, frame):
            # If we're already shutting down, just pass to original handler
            if self._is_shutting_down:
                logger.warning(f"Shutdown already in progress, passing signal {sig} to original handler")
                if sig == signal.SIGTERM and callable(original_term_handler):
                    original_term_handler(sig, frame)
                elif sig == signal.SIGINT and callable(original_int_handler):
                    original_int_handler(sig, frame)
                return

            logger.warning(f"Received signal {sig}, initiating graceful shutdown")

            # Schedule the async shutdown in the event loop
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(
                        self.trigger_shutdown(f"Signal {sig} received")
                    )
                )

                # Give the shutdown a chance to run
                time.sleep(0.5)

                # Then chain to original handler
                if sig == signal.SIGTERM and callable(original_term_handler):
                    original_term_handler(sig, frame)
                elif sig == signal.SIGINT and callable(original_int_handler):
                    original_int_handler(sig, frame)
            except RuntimeError:
                # No event loop, just exit
                logger.warning(f"No event loop running, exiting immediately on signal {sig}")
                sys.exit(0)

        # Install handlers
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        logger.info("Signal handlers installed for graceful shutdown")

    @property
    def shutdown_event(self) -> asyncio.Event:
        """Get the shutdown event that can be awaited to detect shutdown"""
        return self._shutdown_event

# Create a singleton instance
shutdown_manager = ShutdownManager()
