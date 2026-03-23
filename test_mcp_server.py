import asyncio
from mcp import ClientSession, StdioServerParameters, stdio_client

async def test_server():
    server_params = StdioServerParameters(
        command="python3",
        args=["mcp_server.py"],
        env=None
    )
    
    print("Starting MCP server and connecting...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            print("Initializing session...")
            await session.initialize()
            
            print("Listing tools...")
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f"- Tool: {tool.name}")
            
            print("\nTesting 'get_best_practices' tool...")
            result = await session.call_tool("get_best_practices", {"topic": "queues"})
            print(f"Result: {result.content[0].text}")

if __name__ == "__main__":
    asyncio.run(test_server())
