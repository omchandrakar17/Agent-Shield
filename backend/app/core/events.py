"""Application event bus — in-process subscribers and cloud sink."""

from uuid import uuid4

from app.cloud.adapters import get_event_sink
from app.security import now

event_subscribers: list[dict] = []
event_sink = get_event_sink()


def publish_event(event_type: str, data: dict) -> None:
    evt = {"id": str(uuid4()), "type": event_type, "occurred_at": now(), "data": data}
    event_subscribers.append(evt)
    if len(event_subscribers) > 500:
        del event_subscribers[:100]
    event_sink.publish_event(event_type, data)
