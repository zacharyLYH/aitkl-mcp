from typing import Dict, Any, List, Optional
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

class GeminiService:
    def __init__(self):
        # Configure Gemini API
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
        self.model = genai.GenerativeModel('gemini-1.5-flash')

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
                print(f"Warning: Could not convert tool {tool.name}: {e}")
                continue
                
        return available_tools

    def start_chat(self):
        """Start a new chat session"""
        return self.model.start_chat(history=[])

    def send_message(self, chat, message: str, tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        """Send a message to Gemini with optional tools"""
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=1000,
        )
        
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

    def send_tool_result(self, chat, tool_name: str, tool_result: str) -> Any:
        """Send tool result back to Gemini and get response"""
        message = f"Tool {tool_name} returned: {tool_result}"
        return self.send_message(chat, message)

    def process_gemini_response(self, response: Any) -> tuple[List[str], List[str]]:
        """Process Gemini response and extract text and function calls"""
        final_text = []
        tools_used = []
        
        try:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    final_text.append(part.text)
                elif hasattr(part, 'function_call'):
                    tool_name = part.function_call.name
                    tool_args = part.function_call.args
                    tools_used.append(tool_name)
                    
                    # Add tool call info to text
                    final_text.append(f"[Called tool {tool_name} with args {tool_args}]")
        except Exception as e:
            final_text.append(f"Error processing response: {str(e)}")
            
        return final_text, tools_used 