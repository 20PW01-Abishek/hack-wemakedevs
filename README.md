# Lattice

Lattice is a knowledge graph on Neo4j. It answers *why did this change, who decided it, where is it documented, and who is affected*. Every answer comes with the graph path and its source docs. It flags documents that newer decisions have made outdated, and learns from new documents as you add them. Chats are stored in the graph, so new chats can recall earlier ones.

- **Knowledge:** people, concepts (rules, plans, policies, products, teams...), decisions and docs live in one graph. Documents are read by an LLM and merged in (`ingest.py`).
- **Memory:** every Q&A is stored as an `Episode` in a `Session`. Private chats and logins live in `<tenant>-private`; shared chats live in the knowledge graph. The agent's `search_past_chats` tool searches shared chats plus the signed-in user's private ones.
- **Act:** `impact_of` walks concept → related concepts → people → managers, and `create_task` writes follow-up tasks back into the graph.

## Architecture

```
web/ (Next.js)                         api.py (FastAPI)  ->  agent.py / ingest.py / auth.py  ->  Neo4j
  presentation/  components
  domain/        zustand stores
  connectors/    HTTP clients (/api proxy)
```

## Run

```bash
cp vars.sh.example vars.sh      # add ANTHROPIC_API_KEY, or leave it empty to use your local `claude -p` login
source vars.sh && docker compose up -d database   # Neo4j only
uv sync
uv run uvicorn api:app --reload --port 8000
```

In a second terminal:

```bash
cd web && npm install && npm run dev
```

Open http://localhost:3000. The first visit creates the admin account. Others sign up from the login screen (members), and admins manage users on the Users page.

CLI: `uv run python agent.py "What decisions have been made?"`

## Pages

- **New chat** (`/`): ask questions. A Private/Shared switch sits in the chat header and locks once the chat starts.
- **Manage Context** (`/context`): drop or paste documents, sync the `documentation/` folder (admin), remove documents (admin), see outdated-document alerts.
- **Users** (`/users`, admin): add users, change roles, delete users and their private chats.
- The sidebar collapses to an icon rail, lists your chats, and has the signed-in user (with log out) at the bottom.

## Documentation folder

Put `.md`/`.txt`/`.csv` files (any subfolders) in `documentation/`, then `uv run python ingest.py --folder [tenant]` or use "Sync documentation folder" on the Manage Context page (admin). Only new or changed files are re-read.

## Accounts and chats

Passwords are stored as salted scrypt hashes in the private database. `TENANT` in `vars.sh` picks the workspace (a separate Neo4j database pair); create another admin from the CLI with `uv run python auth.py <tenant> <username> --admin`. Chats are private by default. Switch "Shared chat" on before the first message to make a chat visible to everyone and the agent. The 🗑 button deletes a chat.

## Files

- `docker-compose.yml`: Neo4j only; `run.sh`: starts Neo4j, backend and frontend
- `api.py`: FastAPI routes, cookie sessions
- `agent.py`: Neo4j wrapper, LangGraph agent with graph tools, chat sessions and memory
- `uploads/`: original uploaded files (the agent reads them with `read_file` and `query_csv`)
- `ingest.py`: LLM extraction of documents and folders into the graph
- `auth.py`: users and password hashing
- `mcp_server.py`: the same graph tools over MCP (used by the `claude -p` fallback)
- `web/`: Next.js frontend
