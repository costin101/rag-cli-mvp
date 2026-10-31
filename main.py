# main.py
import asyncio
import json
import os
import uuid
from dotenv import load_dotenv
from urllib.parse import parse_qs, urlparse

import websockets

from container import ClaudeDockerManager

load_dotenv()

manager = ClaudeDockerManager(oauth_token=os.environ["API_KEY"], pool_size=3)
manager.start_pool_background()

CLAUDE_TIMEOUT = 300


def run_claude(container, message: str, first: bool) -> str:
    cmd = ["timeout", str(CLAUDE_TIMEOUT), "claude", "-p", message,
           "--output-format", "json", "--dangerously-skip-permissions"]
    if not first:
        cmd.insert(3, "-c")
    res = container.exec_run(cmd, user="node", workdir="/app",
                             environment={"HOME": "/home/node"})
    raw = res.output.decode("utf-8", errors="ignore").strip()
    try:
        return json.loads(raw).get("result") or "No response."
    except Exception:
        return raw or "No response."


async def handler(websocket):
    query = parse_qs(urlparse(websocket.request.path).query)
    session_id = query.get("session", [uuid.uuid4().hex])[0]
    print(f"[+] Connected: {session_id}")

    container = await asyncio.to_thread(manager.acquire)
    first = True
    try:
        async for message in websocket:
            output = await asyncio.to_thread(run_claude, container, message, first)
            first = False
            await websocket.send(output)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        print(f"[-] Disconnected: {session_id}")
        await asyncio.to_thread(manager.release, container)


async def main():
    async with websockets.serve(handler, "localhost", 8000):
        print("Server listening on ws://localhost:8000")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())