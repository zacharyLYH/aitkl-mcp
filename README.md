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
1. `uv run --project client python client/client.py server/server.py`
2. Talk to your server like this: ```curl --location 'http://localhost:8000/query' \
--header 'Content-Type: application/json' \
--data '{
    "query": "Create a travel summary for my trip to Phoenix, Arizona!"
}'``` (Change the "query" portion)

## Troubleshooting
1. Check if client has initialised `curl --location 'http://localhost:8000/health'`
2. Attempt to connect to the server `curl --location 'http://localhost:8000/connect'`
3. Check and see if you can see the list of MCP endpoints created `curl --location 'http://localhost:8000/tools'`

## Suggested order of functions to work
1. `convert_currency()`
2. `get_weather_by_location()`
3. `get_public_holidays()`
4. `get_country_code()`
5. `search_poi()`
6. `get_travel_summary()`

## Suggested questions to ask MCP
1. What public holidays are there in US 2025?
2. Whats the weather like in Phoenix, Arizona?
3. Tell me more about the USA!
4. What restaurants are in Phoenix, Arizona?
5. I'll need 4000USD for my trip. How much is that in malaysian ringgit?
6. Create a travel summary for my trip to Phoenix, Arizona!