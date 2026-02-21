from __future__ import annotations

import argparse
import sys

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MCP stdio smoke test")
    parser.add_argument(
        "--graph",
        default="jwst_graph.json",
        help="Path to graph JSON",
    )
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "codeintel.mcp_server",
            "--graph",
            args.graph,
            "--transport",
            "stdio",
        ],
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            meta = await session.call_tool("metadata")

    payload = meta.structuredContent
    if payload is None and meta.content:
        payload = [item.model_dump() for item in meta.content]

    print({
        "tools": [tool.name for tool in tools.tools],
        "metadata": payload,
    })


if __name__ == "__main__":
    anyio.run(run)
