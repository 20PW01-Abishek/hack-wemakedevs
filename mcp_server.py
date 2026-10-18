import os

from mcp.server.mcpserver import MCPServer

from agent import db, make_tools

server = MCPServer("compbrain")
for t in make_tools(db.select_graph(os.getenv("TENANT", "acme"))):
    server.add_tool(t.func, name=t.name, description=t.description)

if __name__ == "__main__":
    server.run()
