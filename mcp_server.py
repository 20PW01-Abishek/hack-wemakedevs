import os

from mcp.server.mcpserver import MCPServer

from agent import db, make_tools, private_name

server = MCPServer("lattice")
tenant = os.getenv("TENANT", "default")
for t in make_tools(db.create_graph(tenant), os.getenv("USER_NAME", "guest"), db.create_graph(private_name(tenant))):
    server.add_tool(t.func, name=t.name, description=t.description)

if __name__ == "__main__":
    server.run()
