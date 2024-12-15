import asyncio
import socketio
from uvicorn import run
from typing import Tuple
from operational_transform import ot

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = socketio.ASGIApp(sio)
ot_server = ot.OTServer()

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")
    # Send the current doc state
    state = ot_server.get_document_state()
    await sio.emit('doc_state', state, room=sid)

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

@sio.event
async def client_op(sid, data):
    # data might look like: 
    # {
    #   "opId": "...", 
    #   "op_type": "insert",
    #   "position": 5,
    #   "text": "a",
    #   "length": 0,
    #   "base_version": 3
    # }
    op = ot.Operation(
        op_type=data["op_type"],
        position=data["position"],
        text=data.get("text", ""),
        length=data.get("length", 0),
        base_version=data["base_version"],
        op_id=data.get("opId")  # fetch the ID if provided
    )
    asyncio.create_task(ot_server.handle_incoming_operation(op, sio))


# ======== MAIN ENTRY ========

if __name__ == "__main__":
    run(app, host="0.0.0.0", port=8000)
