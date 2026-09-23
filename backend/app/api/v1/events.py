"""Server-sent events stream."""

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.events import event_subscribers

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("")
def events() -> StreamingResponse:
    snapshot = list(event_subscribers)

    def stream():
        cursor = len(snapshot)
        for evt in snapshot:
            yield f"event: {evt['type']}\ndata: {json.dumps(evt)}\n\n"
        while True:
            if len(event_subscribers) > cursor:
                for evt in event_subscribers[cursor:]:
                    yield f"event: {evt['type']}\ndata: {json.dumps(evt)}\n\n"
                cursor = len(event_subscribers)
            else:
                yield ": keep-alive\n\n"
                break

    return StreamingResponse(stream(), media_type="text/event-stream")
