"""Transport-level WebSocket behavior that TestClient does not reproduce."""

import asyncio
import socket
import threading
import time

import pytest
import uvicorn
import websockets
from fastapi import FastAPI

from backend.api.ws import router as ws_router


def test_ws_auth_failure_uses_application_close_code():
    app = FastAPI()
    app.include_router(ws_router)

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.time() + 3
        while not server.started and time.time() < deadline:
            time.sleep(0.02)
        assert server.started, "test WebSocket server failed to start"

        async def connect_without_token():
            try:
                async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
                    await ws.recv()
            except websockets.exceptions.InvalidStatus as exc:
                pytest.fail(
                    "authentication failed during HTTP handshake "
                    f"with status {exc.response.status_code}"
                )
            except websockets.exceptions.ConnectionClosed as exc:
                return exc.rcvd.code if exc.rcvd else None

        close_code = asyncio.run(connect_without_token())
        assert close_code == 4001
    finally:
        server.should_exit = True
        thread.join(timeout=3)
