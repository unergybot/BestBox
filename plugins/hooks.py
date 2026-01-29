"""
Hook runner for lifecycle events.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from .api import HookEvent, HookContext
from .registry import PluginRegistry

logger = logging.getLogger(__name__)


class HookRunner:
    """
    Executes lifecycle hooks in priority order.
    """

    def __init__(self, registry: Optional[PluginRegistry] = None):
        """
        Initialize HookRunner.

        Args:
            registry: PluginRegistry instance (defaults to singleton)
        """
        self.registry = registry or PluginRegistry()
        self._executor = ThreadPoolExecutor(max_workers=4)

    async def run(
        self,
        event: HookEvent,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run all hooks for an event asynchronously.

        Hooks can modify the state, which is passed through the chain.

        Args:
            event: Hook event to trigger
            state: Current agent state (will be modified by hooks)
            metadata: Event-specific metadata

        Returns:
            Modified state after all hooks have run
        """
        if metadata is None:
            metadata = {}

        handlers = self.registry.get_hook_handlers(event.value)

        if not handlers:
            return state

        logger.debug(f"Running {len(handlers)} hooks for {event.value}")

        # Run hooks in priority order
        for handler_info in handlers:
            plugin_name = handler_info["plugin"]
            handler = handler_info["handler"]

            try:
                context = HookContext(
                    event=event,
                    state=state,
                    plugin_name=plugin_name,
                    metadata=metadata
                )

                # Check if handler is async
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(context)
                else:
                    # Run sync handler in executor
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(self._executor, handler, context)

                # If handler returns modified state, use it
                if result is not None and isinstance(result, dict):
                    state = result

            except Exception as e:
                logger.error(
                    f"Error in hook {event.value} from plugin {plugin_name}: {e}",
                    exc_info=True
                )

        return state

    def run_sync(
        self,
        event: HookEvent,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run hooks synchronously.

        Args:
            event: Hook event to trigger
            state: Current agent state
            metadata: Event-specific metadata

        Returns:
            Modified state after all hooks have run
        """
        if metadata is None:
            metadata = {}

        handlers = self.registry.get_hook_handlers(event.value)

        if not handlers:
            return state

        logger.debug(f"Running {len(handlers)} hooks for {event.value} (sync)")

        for handler_info in handlers:
            plugin_name = handler_info["plugin"]
            handler = handler_info["handler"]

            try:
                context = HookContext(
                    event=event,
                    state=state,
                    plugin_name=plugin_name,
                    metadata=metadata
                )

                # Run handler synchronously
                result = handler(context)

                # If handler returns modified state, use it
                if result is not None and isinstance(result, dict):
                    state = result

            except Exception as e:
                logger.error(
                    f"Error in hook {event.value} from plugin {plugin_name}: {e}",
                    exc_info=True
                )

        return state

    def shutdown(self) -> None:
        """Shutdown the thread pool executor."""
        self._executor.shutdown(wait=True)
