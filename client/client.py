from typing import Optional, Dict, Any, List
from contextlib import AsyncExitStack

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from gemini_service import GeminiService

load_dotenv()

# =============================================================================
# Pydantic Models for API Requests/Responses
# =============================================================================

class QueryRequest(BaseModel):
    """Request model for processing queries"""
    query: str

class QueryResponse(BaseModel):
    """Response model for query processing results"""
    response: str
    tools_used: List[str] = []

class ToolInfo(BaseModel):
    """Model representing information about an MCP tool"""
    name: str
    description: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None

class ToolsResponse(BaseModel):
    """Response model for available tools"""
    tools: List[ToolInfo]

# =============================================================================
# MCP Client with Gemini Integration
# =============================================================================

class MCPAPIClient:
    """
    Main client class that manages MCP server connections and integrates with Gemini AI.
    
    This class handles:
    - Connection management to MCP servers
    - Tool discovery and execution
    - Integration with Gemini AI for intelligent query processing
    - Resource cleanup
    """
    
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.gemini_service = GeminiService()
        self.connected_server: Optional[str] = None
        self.server_script_path: Optional[str] = "server/server.py"

    async def connect_to_server(self):
        """
        Connect to an MCP server via stdio transport.
        
        Reuses existing connection if already connected to the same server.
        """
        # Reuse existing connection if already connected to the same server
        if self.connected_server == self.server_script_path and self.session:
            return

        # Clean up existing connection if any
        if self.session:
            await self.cleanup()
            
        # Set up server parameters
        server_params = StdioServerParameters(
            command="python3",
            args=[self.server_script_path],
            env=None
        )
        
        # Establish connection
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        # Initialize the session
        await self.session.initialize()
        self.connected_server = self.server_script_path

    async def get_available_tools(self) -> List[ToolInfo]:
        """
        Get list of available tools from the connected MCP server.
        
        Returns:
            List of ToolInfo objects representing available tools
            
        Raises:
            HTTPException: If not connected to any server
        """
        if not self.session:
            raise HTTPException(status_code=400, detail="Not connected to any server")
            
        response = await self.session.list_tools()
        tools = []
        
        for tool in response.tools: #how to add description and input schema?
            tool_info = ToolInfo(
                name=tool.name,
                description=tool.description,
                input_schema=tool.inputSchema if hasattr(tool, 'inputSchema') else None
            )
            tools.append(tool_info)
            
        return tools

    async def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a query using Gemini AI and available MCP tools.
        
        This method:
        1. Ensures connection to MCP server
        2. Gets available tools and converts them to Gemini format
        3. Sends query to Gemini with available tools
        4. Processes tool calls and executes them
        5. Returns final response with tools used
        
        Args:
            query: The user's query string
            
        Returns:
            Dictionary containing response text and list of tools used
            
        Raises:
            HTTPException: If not connected to server or API errors occur
        """
        if not self.session:
            raise HTTPException(status_code=400, detail="Not connected to any server")
            
        # Initialize Gemini chat session
        chat = self.gemini_service.start_chat()

        # Get available tools and convert to Gemini format
        response = await self.session.list_tools()
        available_tools = self.gemini_service.convert_mcp_tools_to_gemini_format(response.tools)
        tools_used = []

        # Send initial query to Gemini
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

        # Handle tool calls from Gemini
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
        """Clean up resources and close connections"""
        if self.exit_stack:
            await self.exit_stack.aclose()
        self.session = None
        self.connected_server = None

# =============================================================================
# FastAPI Application Setup
# =============================================================================

app = FastAPI(
    title="MCP API Client", 
    description="REST API for MCP client with Gemini integration",
    version="1.0.0"
)

mcp_client = MCPAPIClient()

# =============================================================================
# API Endpoints
# =============================================================================

@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """
    Process a query using the MCP server and Gemini AI.
    
    This endpoint:
    1. Connects to the MCP server if not already connected
    2. Processes the query using Gemini AI with available tools
    3. Returns the response and list of tools used
    """
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
    """
    Get available tools from the MCP server.
    
    Returns a list of all tools that can be used by the MCP server.
    """
    try:
        await mcp_client.connect_to_server()
        tools = await mcp_client.get_available_tools()
        return ToolsResponse(tools=tools)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/connect")
async def connect_to_server():
    """
    Manually connect to an MCP server.
    
    Useful for testing or when you want to ensure a connection
    before making queries.
    """
    try:
        await mcp_client.connect_to_server()    
        return {"message": f"Connected to server"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/disconnect")
async def disconnect_from_server():
    """
    Disconnect from the current MCP server.
    
    Cleans up resources and closes the connection.
    """
    try:
        await mcp_client.cleanup()
        return {"message": "Disconnected from server"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns the current status of the API and connection state.
    """
    return {
        "status": "healthy", 
        "connected": mcp_client.session is not None
    }

# =============================================================================
# Application Entry Point
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 