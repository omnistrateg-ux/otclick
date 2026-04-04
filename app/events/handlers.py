"""Event handlers and dispatcher.

Обрабатывает события и запускает соответствующие Celery tasks.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.events.definitions import Event, EventType

logger = logging.getLogger(__name__)

# Type for event handler functions
EventHandler = Callable[[Event], Awaitable[None]]


class EventDispatcher:
    """Dispatches events to registered handlers.

    Events are processed asynchronously via Celery tasks.
    Handlers are registered by event type.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._global_handlers: list[EventHandler] = []

    def register(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:
        """Register a handler for an event type.

        Args:
            event_type: Type of event to handle
            handler: Async function to call when event occurs
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Registered handler {handler.__name__} for {event_type}")

    def register_global(self, handler: EventHandler) -> None:
        """Register a handler for all events.

        Args:
            handler: Async function to call for any event
        """
        self._global_handlers.append(handler)
        logger.debug(f"Registered global handler {handler.__name__}")

    def unregister(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:
        """Unregister a handler.

        Args:
            event_type: Type of event
            handler: Handler to remove
        """
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    async def dispatch(self, event: Event) -> list[Exception]:
        """Dispatch an event to all registered handlers.

        Args:
            event: Event to dispatch

        Returns:
            List of exceptions from failed handlers
        """
        errors: list[Exception] = []

        # Get handlers for this event type
        handlers = self._handlers.get(event.event_type, [])
        all_handlers = handlers + self._global_handlers

        if not all_handlers:
            logger.debug(f"No handlers registered for {event.event_type}")
            return errors

        logger.info(
            f"Dispatching {event.event_type} to {len(all_handlers)} handlers"
        )

        # Call all handlers
        for handler in all_handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.exception(
                    f"Handler {handler.__name__} failed for {event.event_type}: {e}"
                )
                errors.append(e)

        return errors

    def get_handlers(self, event_type: EventType) -> list[EventHandler]:
        """Get all handlers for an event type.

        Args:
            event_type: Type of event

        Returns:
            List of handler functions
        """
        return self._handlers.get(event_type, []) + self._global_handlers


# Global dispatcher instance
_dispatcher: EventDispatcher | None = None


def get_dispatcher() -> EventDispatcher:
    """Get the global event dispatcher.

    Returns:
        EventDispatcher instance
    """
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = EventDispatcher()
    return _dispatcher


def on_event(event_type: EventType) -> Callable[[EventHandler], EventHandler]:
    """Decorator to register an event handler.

    Args:
        event_type: Type of event to handle

    Returns:
        Decorator function
    """

    def decorator(handler: EventHandler) -> EventHandler:
        get_dispatcher().register(event_type, handler)
        return handler

    return decorator


async def emit_event(event: Event) -> list[Exception]:
    """Emit an event to the global dispatcher.

    Args:
        event: Event to emit

    Returns:
        List of exceptions from failed handlers
    """
    return await get_dispatcher().dispatch(event)


# Standard event handlers registry
# Maps event types to Celery task names
EVENT_TASK_MAPPING: dict[EventType, str] = {
    EventType.LEAD_DISCOVERED: "workers.discovery_tasks.enrich_lead",
    EventType.LEAD_ENRICHED: "workers.discovery_tasks.score_lead",
    EventType.LEAD_SCORED: "workers.outreach_tasks.start_outreach",
    EventType.LEAD_QUALIFIED: "workers.outreach_tasks.schedule_followup",
    EventType.EMAIL_SENT: "workers.analysis_tasks.track_email_delivery",
    EventType.REPLY_RECEIVED: "workers.analysis_tasks.analyze_reply",
    EventType.REPLY_ANALYZED: "workers.analysis_tasks.qualify_lead",
    EventType.QUALIFICATION_COMPLETED: "workers.outreach_tasks.handle_qualification_result",
    EventType.HANDOFF_CREATED: "workers.outreach_tasks.notify_manager",
}


def setup_default_handlers(celery_app: Any) -> None:
    """Set up default event handlers using Celery tasks.

    Args:
        celery_app: Celery application instance
    """
    dispatcher = get_dispatcher()

    for event_type, task_name in EVENT_TASK_MAPPING.items():

        async def create_handler(
            task: str,
        ) -> Callable[[Event], Awaitable[None]]:
            async def handler(event: Event) -> None:
                # Queue the Celery task
                celery_app.send_task(
                    task,
                    kwargs={
                        "event_id": event.id,
                        "event_type": event.event_type.value,
                        "lead_id": event.lead_id,
                        "email_id": event.email_id,
                        "data": event.data,
                    },
                )

            return handler

        import asyncio

        handler = asyncio.get_event_loop().run_until_complete(
            create_handler(task_name)
        )
        dispatcher.register(event_type, handler)

    logger.info(f"Registered {len(EVENT_TASK_MAPPING)} default event handlers")
