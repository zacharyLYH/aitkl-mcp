# aitkl-mcp

## Prereq
1. `uv` package. pip and conda doesn't have the mcp package we'll be needing
- Non-windows: `curl -LsSf https://astral.sh/uv/install.sh | sh` 
- Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
2. Python version > 3.9

## Client
Non-windows
`uv init client && cd client && uv venv && source .venv/bin/activate && uv add mcp anthropic python-dotenv && rm -rf main.py && touch client.py && cd ..`
Windows
`uv init client && cd client && uv venv && .venv\Scripts\activate && uv add mcp anthropic python-dotenv && del main.py && touch client.py && cd ..`

## Server
Non-windows
`uv init server && cd server && uv venv && source .venv/bin/activate && uv add "mcp[cli]" httpx && rm -rf main.py && touch server.py && cd ..`
Windows
`uv init server && cd server && uv venv && .venv\Scripts\activatee && uv add mcp[cli] httpx && del main.py && touch server.py && cd ..`

## Run
`uv run client.py ../server/server.py`