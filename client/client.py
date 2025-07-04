from typing import Optional, Dict, Any, List
from contextlib import AsyncExitStack

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv
import logging

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from gemini_service import GeminiService

load_dotenv()

# =============================================================================
# Configuration
# =============================================================================

DEFAULT_SERVER_PATH = "server/server.py"
DEFAULT_PYTHON_COMMAND = "python3"
API_HOST = "0.0.0.0"
API_PORT = 8000

# =============================================================================
# Logging Setup
# =============================================================================

# Configure logging to show on terminal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger("client.py")

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
        self.server_script_path: Optional[str] = DEFAULT_SERVER_PATH

    async def connect_to_server(self):
        """
        Connect to an MCP server via stdio transport.
        
        Reuses existing connection if already connected to the same server.
        """
        if self._is_already_connected():
            return

        # Clean up existing connection if any
        await self._cleanup_existing_connection()
        await self._establish_new_connection()

    def _is_already_connected(self) -> bool:
        return (self.connected_server == self.server_script_path and 
                self.session is not None)

    async def _cleanup_existing_connection(self):
        if self.session:
            await self.cleanup()

    async def _establish_new_connection(self):
        # Set up server parameters
        server_params = StdioServerParameters(
            command=DEFAULT_PYTHON_COMMAND,
            args=[self.server_script_path],
            env=None
        )
        
        # Establish connection
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )
        
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
        self._ensure_connected()
        
        server_response = await self.session.list_tools()
        tools = []
        
        for tool in server_response.tools:
            tool_info = ToolInfo(
                name=tool.name,
                description=tool.description,
                input_schema=getattr(tool, 'inputSchema', None)
            )
            tools.append(tool_info)
            
        return tools

    def _ensure_connected(self):
        if not self.session:
            raise HTTPException(status_code=400, detail="Not connected to any server")

    async def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a query using Gemini AI and available MCP tools.
        
        This method:
        1. Ensures connection to MCP server
        2. Initializes chat session and gets available tools
        3. Determines which tools to use via Gemini
        4. Executes tool calls and processes results
        5. Returns final response with tools used
        
        Args:
            query: The user's query string
            
        Returns:
            Dictionary containing response text and list of tools used
            
        Raises:
            HTTPException: If not connected to server or API errors occur
        """
        self._ensure_connected()

        # Initialize Gemini chat session and get available tools in server.py
        chat_session = self.gemini_service.start_chat()
        server_response = await self.session.list_tools()
        available_tools = self.gemini_service.convert_mcp_tools_to_gemini_format(server_response.tools)
        
        # Determine which tools to use
        gemini_response = await self.ask_gemini_which_tool_to_use(chat_session, query, available_tools)
        
        # Execute tool calls and get results
        final_response, tools_used = await self._execute_tool_and_gemini_summarise(chat_session, gemini_response)

        return {
            "response": self._format_final_response(final_response),
            "tools_used": tools_used
        }

    async def ask_gemini_which_tool_to_use(self, chat_session, query: str, available_tools):
        """
        Send query to Gemini and get response with potential tool calls.
        
        Args:
            chat_session: The Gemini chat session
            query: The user's query string
            available_tools: List of available tools in Gemini format
            
        Returns:
            The initial response from Gemini
        """
        # Send initial query to Gemini
        try:
            if available_tools:
                return self.gemini_service.send_message(chat_session, query, available_tools)
            else:
                return self.gemini_service.send_message(chat_session, query)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error calling Gemini API: {str(e)}")

    async def _execute_tool_and_gemini_summarise(self, chat_session, gemini_response):
        """
        Execute tool calls from Gemini response and send results back.
        
        Args:
            chat_session: The Gemini chat session
            gemini_response: The initial response from Gemini
            
        Returns:
            Tuple of (final_text_list, tools_used_list)
        """
        response_parts = []
        tools_used = []

        try:
            logger.info(f"Processing Gemini response: {gemini_response}")
            
            for part in gemini_response.candidates[0].content.parts:
                if hasattr(part, 'function_call'):
                    part_response, tool_name = await self._execute_tool_call(chat_session, part)
                    response_parts.append(part_response)
                    tools_used.append(tool_name)
                elif hasattr(part, 'text'):
                    response_parts.append(part.text)
                else:
                    response_parts.append(f"Unknown response type: {str(part)}")
                    
        except Exception as e:
            response_parts.append(f"Error processing response: {str(e)}")

        return response_parts, tools_used

    async def _execute_tool_call(self, chat_session, function_call_part):
        tool_name = function_call_part.function_call.name
        tool_args = function_call_part.function_call.args

        # Optional: Add tool execution timeout to prevent hanging
        # Execute tool call
        try:
            tool_result = await self.session.call_tool(tool_name, tool_args)
            logger.info(f"\n\nTool '{tool_name}' executed successfully\n\n")

            # Continue conversation with tool calling results
            gemini_interpretation = self.gemini_service.send_tool_result(
                chat_session, tool_name, tool_result.content
            )
            return gemini_interpretation.text, tool_name
            
        except Exception as e:
            error_message = f"Tool '{tool_name}' failed: {str(e)}"
            logger.error(error_message)
            return error_message, tool_name

    def _format_final_response(self, response_parts: List[str]) -> str:
        if not response_parts:
            return "No response generated"
        return "\n".join(response_parts)
    
    async def cleanup(self):
        """Clean up resources and close connections"""
        try:
            if self.exit_stack:
                await self.exit_stack.aclose()
        except Exception as e:
            logger.error(f"Warning: Error during cleanup: {e}")
        finally:
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
        return {"message": "Connected to server"}
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
    uvicorn.run(app, host=API_HOST, port=API_PORT)
