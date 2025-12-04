from server import mcp  # reuse the same FastMCP instance and tools

if __name__ == "__main__":
    # Default transport is stdio; we can be explicit:
    mcp.run(transport="stdio")