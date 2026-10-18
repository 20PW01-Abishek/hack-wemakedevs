# Comp Brain

A company brain for sales compensation, built on FalkorDB. It answers *why did this rule change, who decided it, where is it documented, and who is affected*. Every answer comes with the graph path and its source docs. It flags documents that newer decisions have made outdated, and learns from new documents as you add them. It also remembers each user across sessions.

- **Track 3 (Company Brain):** people, teams, plans, rules, decisions and docs live in one graph. New docs are read by an LLM and merged in live (`ingest.py`).
- **Track 2 (Memory):** every Q&A is stored as an `Episode` linked to the user and the entities it touched, and recalled in later sessions. Each tenant gets its own graph.
- **Track 1 (Act):** `impact_of` walks rule → plans → people → managers, and `create_task` writes follow-up tasks back into the graph.

## Run locally

```bash
docker run -d -p 6379:6379 -p 3000:3000 -v falkordb_data:/var/lib/falkordb/data falkordb/falkordb:latest
cp .env.example .env            # add ANTHROPIC_API_KEY, or leave it empty to use your local `claude -p` login
uv sync
uv run python seed.py           # loads data/company.json into graph "acme"
uv run streamlit run app.py
```

CLI: `uv run python agent.py "Who is affected if the AE accelerator changes?"`
Graph browser: http://localhost:3000

## Files

- `data/company.json`: fake company data (org, plans, rules, docs, decisions)
- `seed.py`: loads it into FalkorDB (`uv run python seed.py <graph>` for another tenant)
- `agent.py`: LangGraph agent with graph tools and episodic memory
- `ingest.py`: LLM extraction of a new document into the graph (`uv run python ingest.py <title> <author> <text>`)
- `app.py`: Streamlit chat UI with outdated-doc alerts, an add-document form and the answer path drawn as a graph
- `mcp_server.py`: the same graph tools over MCP (used by the `claude -p` fallback, or plug it into any MCP client)
