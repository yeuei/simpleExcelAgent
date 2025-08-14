from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Weather", port = 8009)

@mcp.tool()
async def get_weather(location: str) -> str:
    """Get weather for location."""
    return "It's always sunny in New York"

if __name__ == "__main__":
    mcp.run(transport="streamable-http")