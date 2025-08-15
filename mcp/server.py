from typing import Any


def create_server() -> Any:
    """Create and return a FastMCP server instance.

    This is a stub to be expanded with real skill registration.
    """
    try:
        from fastmcp import MCPServer  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("fastmcp is not available. Install dependencies.") from exc

    server = MCPServer(name="hiking-assistant")
    # TODO: register skills from mcp.skills here via server.register(...)
    return server
