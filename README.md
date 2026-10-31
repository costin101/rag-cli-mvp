# rag-cli-mvp

A WebSocket server that gives each connected user an isolated Docker container running the [Claude Code](https://docs.claude.com/en/docs/claude-code) CLI. Messages sent over the socket are executed as `claude -p` inside the user's container, and the reply is sent back. Follow-up messages in the same session continue the conversation (`claude -c`).

A minimal browser client (`index.html`) is included.

## Architecture

```
browser (index.html) ──ws://localhost:8000/?session=<id>──> main.py
                                                              │
                                                  ClaudeDockerManager (container.py)
                                                              │
                                      pool of warm containers (node:22-slim + claude-code)
```

- On startup the server builds the `claude-runner:latest` image and keeps a pool of 3 warm containers.
- Each WebSocket connection acquires one container; it is destroyed on disconnect.
- Containers are limited to 1 GB RAM, 1 CPU, and 256 PIDs.
- Each `claude` call has a 300 s timeout.

## Prerequisites

- Python 3.10+
- Docker, running locally
- Node.js and the Claude Code CLI on the host (only to generate the token)
- A Claude subscription (Pro/Max)

## Setup

### 1. Generate a Claude token

```bash
npm install -g @anthropic-ai/claude-code
claude setup-token
```

Complete the browser login. The command prints a long-lived OAuth token.

### 2. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env` and paste the token:

```
API_KEY=<token from claude setup-token>
```

The server passes this value to each container as `CLAUDE_CODE_OAUTH_TOKEN`.

### 3. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

The first start builds the Docker image, which takes a minute. When ready:

```
Server listening on ws://localhost:8000
```

Open `index.html` in a browser, type a message, and press Enter. Each browser tab gets its own session ID and its own container.

### Using another WebSocket client

```bash
npx wscat -c "ws://localhost:8000/?session=demo"
> list the files in the current directory
```

The `session` query parameter is optional; a random ID is generated if omitted.

## Security notes

- Claude runs with `--dangerously-skip-permissions` inside the container. It can execute arbitrary commands there; the container is the isolation boundary.
- All containers share one OAuth token, so usage counts against a single subscription.
- The server binds to `localhost` and has no authentication. Do not expose it publicly without adding auth.
- Keep `.env` out of version control (it is in `.gitignore`).

## Files

| File | Purpose |
|------|---------|
| `main.py` | WebSocket server, runs `claude` in a container per session |
| `container.py` | Image build and container pool management |
| `index.html` | Browser test client |
| `.env.example` | Template for the required `API_KEY` |
