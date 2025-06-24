from typing import Optional, Dict, Any, List
from contextlib import AsyncExitStack
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from gemini_service import GeminiService

from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

# Pydantic models for API requests/responses
class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    response: str
    tools_used: List[str] = []

class ToolInfo(BaseModel):
    name: str
    description: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None

class ToolsResponse(BaseModel):
    tools: List[ToolInfo]

class MCPAPIClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        # Initialize Gemini service
        self.gemini_service = GeminiService()
        self.connected_server: Optional[str] = None
        self.server_script_path: Optional[str] = "../server/server.py"

    async def connect_to_server(self):
        """Connect to an MCP server"""
        # If already connected to the same server, don't reconnect
        if self.connected_server == self.server_script_path and self.session:
            return

        # Clean up existing connection if any
        if self.session:
            await self.cleanup()
            
        server_params = StdioServerParameters(
            command="python3",
            args=[self.server_script_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        self.connected_server = self.server_script_path

    async def get_available_tools(self) -> List[ToolInfo]:
        """Get list of available tools from the connected server"""
        if not self.session:
            raise HTTPException(status_code=400, detail="Not connected to any server")
            
        response = await self.session.list_tools()
        tools = []
        for tool in response.tools:
            tool_info = ToolInfo(
                name=tool.name,
                description=tool.description,
                input_schema=tool.inputSchema if hasattr(tool, 'inputSchema') else None
            )
            tools.append(tool_info)
        return tools

    async def process_query(self, query: str) -> Dict[str, Any]:
        """Process a query using Gemini and available tools"""
        if not self.session:
            raise HTTPException(status_code=400, detail="Not connected to any server")
            
        chat = self.gemini_service.start_chat()

        response = await self.session.list_tools()
        # Convert MCP tools to Gemini's FunctionDeclaration format
        available_tools = self.gemini_service.convert_mcp_tools_to_gemini_format(response.tools)
        tools_used = []

        # Initial Gemini API call
        try:
            if available_tools:
                response = self.gemini_service.send_message(chat, query, available_tools)
            else:
                response = self.gemini_service.send_message(chat, query)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error calling Gemini API: {str(e)}")

        # Process response and handle tool calls
        final_text, initial_tools_used = self.gemini_service.process_gemini_response(response)
        tools_used.extend(initial_tools_used)

        try:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'function_call'):
                    tool_name = part.function_call.name
                    tool_args = part.function_call.args
                    
                    # Execute tool call
                    try:
                        result = await self.session.call_tool(tool_name, tool_args)

                        # Continue conversation with tool calling results
                        chat.send_message(f"Tool calling result: {result.content}")

                        # Get next response from Gemini
                        next_response = self.gemini_service.send_tool_result(chat, tool_name, result.content)

                        final_text.append(next_response.text)
                    except Exception as e:
                        final_text.append(f"Error executing tool {tool_name}: {str(e)}")
        except Exception as e:
            final_text.append(f"Error processing response: {str(e)}")

        return {
            "response": "\n".join(final_text),
            "tools_used": tools_used
        }
    
    async def cleanup(self):
        """Clean up resources"""
        if self.exit_stack:
            await self.exit_stack.aclose()
        self.session = None
        self.connected_server = None

# Create FastAPI app
app = FastAPI(title="MCP API Client", description="REST API for MCP client with Gemini integration")

# Global client instance
mcp_client = MCPAPIClient()

@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """Process a query using the MCP server and Gemini"""
    try:
        # Connect to server if needed
        await mcp_client.connect_to_server()
        
        # Process the query
        result = await mcp_client.process_query(request.query)
        
        return QueryResponse(
            response=result["response"],
            tools_used=result["tools_used"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tools", response_model=ToolsResponse)
async def get_tools():
    """Get available tools from the MCP server"""
    try:
        await mcp_client.connect_to_server()
        tools = await mcp_client.get_available_tools()
        return ToolsResponse(tools=tools)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/connect")
async def connect_to_server():
    """Connect to an MCP server"""
    try:
        await mcp_client.connect_to_server()    
        return {"message": f"Connected to server"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/disconnect")
async def disconnect_from_server():
    """Disconnect from the current MCP server"""
    try:
        await mcp_client.cleanup()
        return {"message": "Disconnected from server"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "connected": mcp_client.session is not None}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 