# container.py
import io
import os
import queue
import textwrap
import threading
import time

import docker


class ClaudeDockerManager:
    def __init__(self, oauth_token: str, pool_size: int = 3, image_name: str = "claude-runner:latest"):
        self.client = docker.from_env()
        self.oauth_token = oauth_token
        self.pool_size = pool_size
        self.image_name = image_name
        self.pool = queue.Queue()
        self._build_image()

    def _build_image(self):
        dockerfile = textwrap.dedent("""
            FROM node:22-slim
            RUN npm install -g @anthropic-ai/claude-code
            RUN mkdir -p /app && chown node:node /app
            USER node
            ENV HOME=/home/node
            WORKDIR /app
            CMD ["tail", "-f", "/dev/null"]
        """)
        self.client.images.build(
            fileobj=io.BytesIO(dockerfile.encode("utf-8")),
            tag=self.image_name,
            rm=True,
        )

    def _spawn_container(self):
        return self.client.containers.run(
            image=self.image_name,
            environment={
                "CLAUDE_CODE_OAUTH_TOKEN": self.oauth_token,
                "HOME": "/home/node",
            },
            detach=True,
            tty=True,
            mem_limit="1g",
            nano_cpus=1_000_000_000,
            pids_limit=256,
            command="tail -f /dev/null",
        )

    def _maintain_pool(self):
        while True:
            while self.pool.qsize() < self.pool_size:
                try:
                    self.pool.put(self._spawn_container())
                except Exception as e:
                    print(f"[-] Error spawning container: {e}")
                    break
            time.sleep(1)

    def start_pool_background(self):
        threading.Thread(target=self._maintain_pool, daemon=True).start()

    def acquire(self, timeout: float = 60):
        try:
            c = self.pool.get(timeout=timeout)
        except queue.Empty:
            return self._spawn_container()
        try:
            c.reload()
            if c.status != "running":
                c.start()
            return c
        except Exception:
            return self._spawn_container()

    def release(self, container):
        try:
            container.remove(force=True)
        except Exception as e:
            print(f"[-] Error removing container: {e}")