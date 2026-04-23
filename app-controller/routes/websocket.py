from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.deps import ws_manager, logger

websocket_router = APIRouter()


@websocket_router.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    await ws_manager.connect(websocket, channel="monitor")
    logger.info("WebSocket connection established for monitoring")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel="monitor")
        logger.info("WebSocket connection closed")
