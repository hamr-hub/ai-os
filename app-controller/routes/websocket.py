from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from datetime import datetime

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


@websocket_router.websocket("/ws/model-switch")
async def websocket_model_switch(websocket: WebSocket):
    await ws_manager.connect(websocket, channel="model_switch")
    logger.info("WebSocket connected: model_switch channel")

    from core.deps import model_switch_orchestrator
    current = model_switch_orchestrator.current_session
    if current:
        try:
            await websocket.send_json({
                "type": "switch_state_sync",
                "timestamp": datetime.now().isoformat(),
                "session": current.to_dict(),
                "is_switching": model_switch_orchestrator.is_switching,
            })
        except Exception:
            pass

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel="model_switch")
        logger.info("WebSocket disconnected: model_switch channel")
