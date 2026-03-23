import os
import asyncio
import gradio as gr
from ollama import AsyncClient
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, stdio_client

# Load environment variables
load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
MCP_SERVER_SCRIPT = "mcp_server.py"

async def get_mcp_tools():
    """Starts the MCP server and fetches available tools."""
    server_params = StdioServerParameters(
        command="python3",
        args=[MCP_SERVER_SCRIPT]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return tools

async def call_mcp_tool(name, arguments):
    """Starts the MCP server, calls a specific tool, and returns the result."""
    server_params = StdioServerParameters(
        command="python3",
        args=[MCP_SERVER_SCRIPT]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            return result.content[0].text if result.content else "No result from tool."

def format_tools_for_ollama(mcp_tools):
    """Formats MCP tools into Ollama's tool format."""
    ollama_tools = []
    for tool in mcp_tools.tools:
        ollama_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        })
    return ollama_tools

async def chat_with_rabbitmq_expert(message, history):
    """Main chat function that handles user input, tool calling, and response generation."""
    
    # 1. Get MCP Tools
    try:
        mcp_tools_resp = await get_mcp_tools()
        ollama_tools = format_tools_for_ollama(mcp_tools_resp)
    except Exception as e:
        yield "Error connecting to MCP Server: " + str(e)
        return

    # 2. Prepare Messages
    messages = [{"role": "system", "content": "You are a RabbitMQ Expert. You have access to tools that can check the cluster status, list queues, find issues, and provide best practices. Use these tools to help the user."}]
    
    # Add history
    for msg in history:
        messages.append(msg)
    
    # Add current message
    messages.append({"role": "user", "content": message})

    # 3. Initial call to Ollama with tools
    try:
        client = AsyncClient()
        response = await client.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            tools=ollama_tools
        )
    except Exception as e:
        yield f"Error calling Ollama: {str(e)}"
        return

    # 4. Handle tool calls
    if response.get("message", {}).get("tool_calls"):
        messages.append(response["message"])
        
        for tool_call in response["message"]["tool_calls"]:
            tool_name = tool_call["function"]["name"]
            tool_args = tool_call["function"]["arguments"]
            
            yield f"*Calling tool: {tool_name}({tool_args})...*"
            
            # Call the actual MCP tool
            try:
                tool_result = await call_mcp_tool(tool_name, tool_args)
            except Exception as e:
                tool_result = f"Error calling tool {tool_name}: {str(e)}"
            
            messages.append({
                "role": "tool",
                "content": tool_result,
            })
        
        # 5. Final response from Ollama after tools
        final_response = await client.chat(
            model=OLLAMA_MODEL,
            messages=messages
        )
        yield final_response["message"]["content"]
    else:
        yield response["message"]["content"]

# Gradio UI
with gr.Blocks(title="RabbitMQ Expert Assistant") as demo:
    gr.Markdown("# 🐰 RabbitMQ Expert Assistant")
    gr.Markdown("I can help you monitor and optimize your RabbitMQ cluster. Ask me about queues, users, alerts, or best practices!")
    
    chatbot = gr.ChatInterface(
        fn=chat_with_rabbitmq_expert,
        type="messages"
    )

if __name__ == "__main__":
    demo.launch()
