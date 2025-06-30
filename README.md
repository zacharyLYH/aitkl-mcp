# aitkl-mcp

A travel assistant MCP (Model Context Protocol) project that provides AI-powered travel services including currency conversion, weather data, public holidays, points of interest, and travel summaries through a client-server architecture.

## Prerequisites for all OS'

1. **`uv` package** - pip and conda don't have the MCP package we'll be needing
   - **Non-Windows**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - **Windows**: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

2. **Python version** > 3.9

## MCP project setup

### Client Setup

**Non-Windows:**
```bash
uv init client && cd client && uv venv && source .venv/bin/activate && uv add mcp anthropic python-dotenv && rm -rf main.py && touch client.py && cd ..
```

**Windows:**
```bash
uv init client && cd client && uv venv && .venv\Scripts\activate && uv add mcp anthropic python-dotenv && del main.py && touch client.py && cd ..
```

### Server Setup

**Non-Windows:**
```bash
uv init server && cd server && uv venv && source .venv/bin/activate && uv add "mcp[cli]" httpx && rm -rf main.py && touch server.py && cd ..
```

**Windows:**
```bash
uv init server && cd server && uv venv && .venv\Scripts\activate && uv add "mcp[cli]" httpx && del main.py && touch server.py && cd ..
```

## Running the Application

1. **Start the application:**
   ```bash
   uv run --project client python client/client.py server/server.py
   ```

2. **Create a `.env` file** with the following content:
   ```env
   GEMINI_API_KEY=abc123
   GEMINI_MODEL_NAME=gemini-2.0-flash
   ```
   > **Note**: Refer to [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) for the list of models and their limits.

3. **Get a Gemini API key** from [Google AI Studio](https://aistudio.google.com/apikey) and paste it in the `.env` file.

4. **Test the server** with a sample query:
   ```bash
   curl --location 'http://localhost:8000/query' \
   --header 'Content-Type: application/json' \
   --data '{
       "query": "Create a travel summary for my trip to Phoenix, Arizona!"
   }'
   ```

## Troubleshooting

1. **Check if client has initialized:**
   ```bash
   curl --location 'http://localhost:8000/health'
   ```

2. **Attempt to connect to the server:**
   ```bash
   curl --location 'http://localhost:8000/connect'
   ```

3. **Check available MCP endpoints:**
   ```bash
   curl --location 'http://localhost:8000/tools'
   ```

## Development Guide

### Suggested Order of Functions to Implement

1. `convert_currency()`
2. `get_weather_by_location()`
3. `get_public_holidays()`
4. `get_country_code()`
5. `search_poi()`
6. `get_travel_summary()`

### Sample Questions to Test MCP

1. What public holidays are there in US 2025?
2. What's the weather like in Phoenix, Arizona?
3. Tell me more about the USA!
4. What restaurants are in Phoenix, Arizona?
5. I'll need 4000 USD for my trip. How much is that in Malaysian Ringgit?
6. Create a travel summary for my trip to Phoenix, Arizona!