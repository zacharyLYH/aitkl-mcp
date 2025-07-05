from typing import Dict, Any, List, Optional
import os
import google.generativeai as genai
from dotenv import load_dotenv
import logging

# Configure logging to show on terminal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

log = logging.getLogger("gemini_service.py")

load_dotenv()  # load environment variables from .env

class GeminiService:
    def __init__(self):
        api_key = os.getenv('GEMINI_API_KEY')  
        if not api_key:
            log.error("GEMINI_API_KEY environment variable is required")
            raise ValueError("GEMINI_API_KEY environment variable is required")

        # Configure Gemini API
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(os.getenv('GEMINI_MODEL_NAME'))
            log.info("Gemini service initialized successfully")
        except Exception as e:
            log.error(f"Error initializing Gemini service: {e}")
            raise

    def convert_mcp_tools_to_gemini_format(self, mcp_tools: List[Any]) -> List[Dict[str, Any]]:
        """Convert MCP tools to Gemini's FunctionDeclaration format"""

        available_tools = []
        
        for tool in mcp_tools:
            try:
                # Convert inputSchema to Gemini's expected format
                parameters = {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
                
                if hasattr(tool, 'inputSchema') and tool.inputSchema:
                    # Convert JSON schema to Gemini's parameter format
                    if isinstance(tool.inputSchema, dict):
                        # Clean up properties to only include Gemini-supported fields
                        clean_properties = {}
                        if 'properties' in tool.inputSchema:
                            for prop_name, prop_schema in tool.inputSchema['properties'].items():
                                if isinstance(prop_schema, dict):
                                    # Only include fields that Gemini supports
                                    clean_prop = {}
                                    if 'type' in prop_schema:
                                        clean_prop['type'] = prop_schema['type']
                                    if 'description' in prop_schema:
                                        clean_prop['description'] = prop_schema['description']
                                    if 'enum' in prop_schema:
                                        clean_prop['enum'] = prop_schema['enum']
                                    # Add other supported fields as needed
                                    clean_properties[prop_name] = clean_prop
                        
                        parameters = {
                            "type": "object",
                            "properties": clean_properties,
                            "required": tool.inputSchema.get("required", [])
                        }
                
                gemini_tool = {
                    "function_declarations": [{
                        "name": tool.name,
                        "description": tool.description or f"Tool: {tool.name}",
                        "parameters": parameters
                    }]
                }
                available_tools.append(gemini_tool)
            except Exception as e:
                log.error(f"Error converting tool {tool.name}: {e}")
                continue
                
        log.info(f"Successfully converted {len(available_tools)} tools to Gemini format")
        return available_tools

    def start_chat(self):
        """Start a new chat session"""
        return self.model.start_chat(history=[])

    def send_message(self, chat, message: str, tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        """Send a message to Gemini with optional tools"""
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=1000,
        )
        
        try:
            if tools:
                return chat.send_message(
                    message,
                    generation_config=generation_config,
                    tools=tools
                )
            else:
                return chat.send_message(
                    message,
                    generation_config=generation_config
                )
        except Exception as e:
            log.error(f"Error sending message to Gemini: {e}")
            raise

    def send_tool_result(self, chat, tool_name: str, tool_result: str) -> Any:
        """Send tool result back to Gemini and get response"""
        try:
            message = f"Tool {tool_name} returned: {tool_result}"
            return self.send_message(chat, message)
        except Exception as e:
            log.error(f"Error sending tool result for {tool_name}: {e}")
            raise
