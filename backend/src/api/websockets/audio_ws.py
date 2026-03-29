"""Bidirectional WebSocket endpoint for Telnyx audio streaming.

Robustness features:
- Heartbeat: native WS ping every 20s to keep connection alive through proxies
- Receive timeout: aligned with MAX_CALL_DURATION to detect zombie sockets
- Backpressure: send queue has maxsize, drops oldest chunk when full
- Reconnexion: on disconnect, delegates to telephony.on_ws_disconnect() which
  may retry start_streaming() — if a new WS connects within 5s, audio resumes
- Structured logging: connect/disconnect with duration and chunk counts
"""

import asyncio
import base64
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.src.api.dependencies import get_telephony
from backend.src.infrastructure.audio.pipeline import MAX_CALL_DURATION

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Heartbeat interval and pong timeout (seconds)
HEARTBEAT_INTERVAL = 20
PONG_TIMEOUT = 5


@router.websocket("/ws/audio/{call_control_id}")
async def audio_websocket(websocket: WebSocket, call_control_id: str):
    """Handle bidirectional audio streaming with Telnyx.

    Inbound: Telnyx sends JSON with base64 audio -> decoded and fed to telephony adapter.
    Outbound: TTS audio queued via send_audio() -> encoded as base64 and sent to Telnyx.
    """
    await websocket.accept()
    telephony = get_telephony()
    send_queue = telephony.get_send_queue(call_control_id)

    # Notify the adapter that a WS is connected (used by reconnexion logic)
    telephony.on_ws_connected(call_control_id)

    t_connect = time.monotonic()
    chunks_received = 0
    chunks_sent = 0
    bytes_received = 0
    bytes_sent = 0

    logger.debug("WS connected for call %s", call_control_id)

    async def _heartbeat_loop():
        """Send native WS pings to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                try:
                    await asyncio.wait_for(
                        websocket.send({"type": "websocket.ping", "bytes": b""}),
                        timeout=PONG_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "WS pong timeout for call %s — closing", call_control_id
                    )
                    await websocket.close(code=1001)
                    return
                except Exception:
                    return  # WS already closed
        except asyncio.CancelledError:
            pass

    async def _send_loop():
        """Read from the send queue and forward to Telnyx as base64 JSON."""
        nonlocal chunks_sent, bytes_sent
        try:
            while True:
                chunk = await send_queue.get()
                if chunk is None:
                    break
                payload = base64.b64encode(chunk).decode("ascii")
                message = json.dumps({
                    "event": "media",
                    "media": {"payload": payload},
                })
                await websocket.send_text(message)
                chunks_sent += 1
                bytes_sent += len(chunk)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(
                "WS send loop error for call %s: %s", call_control_id, e
            )

    heartbeat_task = asyncio.create_task(_heartbeat_loop())
    send_task = asyncio.create_task(_send_loop())

    try:
        while True:
            # Receive with timeout aligned to max call duration
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=MAX_CALL_DURATION,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "WS receive timeout (%ds) for call %s — closing",
                    MAX_CALL_DURATION,
                    call_control_id,
                )
                break

            data = json.loads(raw)

            if data.get("event") == "media":
                b64_payload = data.get("media", {}).get("payload", "")
                if b64_payload:
                    audio_bytes = base64.b64decode(b64_payload)
                    telephony.feed_audio(call_control_id, audio_bytes)
                    chunks_received += 1
                    bytes_received += len(audio_bytes)
            else:
                logger.debug(
                    "WS non-media event for call %s: %s",
                    call_control_id,
                    data.get("event"),
                )
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WS receive error for call %s: %s", call_control_id, e)
    finally:
        # Cancel background tasks
        heartbeat_task.cancel()
        send_task.cancel()
        for task in (heartbeat_task, send_task):
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        # Log session stats
        duration = time.monotonic() - t_connect
        logger.info(
            "WS closed %s — %.0fs, in=%d out=%d chunks",
            call_control_id[:20],
            duration,
            chunks_received,
            chunks_sent,
        )

        # Delegate to telephony adapter for reconnexion or cleanup
        reconnected = await telephony.on_ws_disconnect(call_control_id)
        if not reconnected:
            logger.info(
                "No reconnexion for call %s — audio permanently ended",
                call_control_id,
            )
