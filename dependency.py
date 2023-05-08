import asyncio
from typing import Optional
from fastapi import FastAPI, Cookie, WebSocket, WebSocketDisconnect, status

# import app
from broadcaster import Broadcast
from pydantic import BaseModel


broadcast = Broadcast("redis://localhost:6379")
CHANNEL = "CHAT"
app = FastAPI()


class MessageEvent(BaseModel):
    username: str
    message: str


async def receive_message(websocket: WebSocket, username: str):
    async with broadcast.subscribe(CHANNEL) as subscriber:
        async for event in subscriber:
            message_event = MessageEvent.parse_raw(event.message)

            if message_event.username != username:
                await websocket.send_json(message_event.dict())


async def send_message(websocket: WebSocket, username: str):
    data = await websocket.receive_text()
    event = MessageEvent(username=username, message=data)
    await broadcast.publish(channel=CHANNEL, message=event.json())


API_TOKEN = "SECRET_API_TOKEN"


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    username: str = "Anonymous",
):
    await websocket.accept()
    try:
        while True:
            receive_message_task = asyncio.create_task(
                receive_message(websocket, username)
            )
            send_message_task = asyncio.create_task(send_message(websocket, username))
            done, pending = await asyncio.wait(
                {receive_message_task, send_message_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in done:
                task.result()
    except WebSocketDisconnect:
        await websocket.close()


@app.on_event("startup")
async def startup():
    await broadcast.connect()


@app.on_event("shutdown")
async def shutdown():
    await broadcast.disconnect()
