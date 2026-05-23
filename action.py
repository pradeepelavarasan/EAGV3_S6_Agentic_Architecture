import sys
from typing import Optional, Dict, Any, List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import artifacts

async def get_tools() -> List[dict]:
    """Retrieve available tools from the MCP server."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"]
    )
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_res = await session.list_tools()
                return [
                    {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": t.inputSchema
                    } for t in tools_res.tools
                ]
    except Exception as e:
        print(f"[Action Error] Failed to list tools: {e}")
        return []

async def execute(tool_name: str, tool_args: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[str]]:
    """
    Executes a tool via the MCP server.
    Returns (outcome_dict, artifact_id).
    Safety Guard: Blocks 'art:...' arguments.
    Outputs > 4KB go to artifacts.put().
    """
    # Safety Guard
    for k, v in tool_args.items():
        if isinstance(v, str) and v.startswith("art:"):
            return {"error": f"Security Exception: Passing artifact handles directly is prohibited. Tool argument '{k}' contained {v}."}, None

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"]
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool(tool_name, tool_args)
                
                outcome_text = ""
                if result.content:
                    outcome_text = result.content[0].text
                
                if result.isError:
                    return {"error": outcome_text}, None
                    
                # Size check
                raw_bytes = outcome_text.encode('utf-8')
                if len(raw_bytes) > 4000:
                    art_id = artifacts.put(
                        blob=raw_bytes,
                        content_type="text/plain",
                        source=f"tool:{tool_name}",
                        descriptor=f"Output from {tool_name}"
                    )
                    return {"summary": f"Output was too large. Saved as artifact {art_id}."}, art_id
                else:
                    return {"result": outcome_text}, None
                    
    except Exception as e:
        print(f"[Action Error] {e}")
        return {"error": str(e)}, None
