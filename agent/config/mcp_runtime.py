from pathlib import Path


def get_cloud_platform_mcp_connections() -> dict:
    """Build a portable MCP config for the local cloud platform server."""
    agent_root = Path(__file__).resolve().parents[1]
    preferred_python = agent_root / ".venv" / "bin" / "python"
    server_path = agent_root / "mcp_servers" / "cloud_platform_server.py"

    return {
        "cloud_platform": {
            "command": str(preferred_python) if preferred_python.exists() else "python",
            "args": [str(server_path)],
            "transport": "stdio",
        }
    }
