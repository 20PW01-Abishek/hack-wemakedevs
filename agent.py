import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import duckdb
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from neo4j import GraphDatabase, RoutingControl

load_dotenv()
MODEL = os.getenv("MODEL", "claude-sonnet-5-5")
HERE = os.path.dirname(os.path.abspath(__file__))


class Graph:
    """One Neo4j database per tenant."""

    def __init__(self, driver, name):
        self.driver, self.name = driver, name

    def _run(self, cypher, params, routing):
        records, _, _ = self.driver.execute_query(cypher, params or {}, database_=self.name, routing_=routing)
        return type("Result", (), {"result_set": [list(r.values()) for r in records]})

    def query(self, cypher, params=None):
        return self._run(cypher, params, RoutingControl.WRITE)

    def ro_query(self, cypher, params=None):
        return self._run(cypher, params, RoutingControl.READ)


class DB:
    def __init__(self):
        self.driver = GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                                           auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password")),
                                           notifications_min_severity="OFF")

    def list_graphs(self):
        rows, _, _ = self.driver.execute_query("SHOW DATABASES YIELD name", database_="system")
        return sorted(r["name"] for r in rows if r["name"] not in ("system", "neo4j"))

    def select_graph(self, name):
        return Graph(self.driver, name)

    def create_graph(self, name):
        self.driver.execute_query("CREATE DATABASE $n IF NOT EXISTS WAIT", {"n": name}, database_="system")
        g = self.select_graph(name)
        g.query("CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (c:Chunk) ON EACH [c.text]")
        return g


db = DB()

SYSTEM = """You are Lattice, a knowledge agent for an organisation: its people, concepts (rules, plans, policies, products, projects, teams...), decisions and documents.
All company knowledge lives in a Neo4j graph. Answer only from what the tools return; never invent facts.

Graph schema (read live from the graph):
{schema}

How to answer:
- Start with find_entity to resolve names. If several match, pick from context or ask which one.
- For "why/who decided/what changed" questions use decisions_for.
- For "who is affected if X changes" use impact_of.
- For "is our documentation up to date / what is outdated" use find_stale_docs. When you notice a doc that contradicts a newer decision, warn the user.
- For questions about documentation content, policies or how things are linked, use search_docs, then follow the graph from the entities it mentions.
- For exact figures in a CSV (counts, totals, lookups) use query_csv; to read a document in full use read_file. Never count or add rows by eye.
- When the user refers to earlier conversations ("as we discussed", "last time"), use search_past_chats.
- Use run_cypher only when no other tool fits.
- End every answer with a "Path:" line showing the graph path (A -> B -> C) and a "Sources:" line with doc titles and URLs.

{memory}"""


def schema(g):
    # ponytail: full scan of nodes and edges, cache or sample when the graph gets large
    props = g.ro_query("MATCH (n) UNWIND keys(n) AS k RETURN labels(n)[0], collect(DISTINCT k)").result_set
    edges = g.ro_query("MATCH (a)-[r]->(b) RETURN DISTINCT labels(a)[0], type(r), labels(b)[0]").result_set
    return "\n".join([f"(:{l} {{{','.join(sorted(ks))}}})" for l, ks in sorted(props)] +
                     [f"(:{a})-[:{r}]->(:{b})" for a, r, b in sorted(edges)])


def text_of(content):
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")


def make_tools(g, user="guest", pg=None):
    def q(cypher, params=None):
        return g.ro_query(cypher, params or {}).result_set

    def rows(cypher, params):
        return [" | ".join(map(str, r)) for r in q(cypher, params)]

    @tool
    def find_entity(name: str) -> list:
        """Find nodes whose name contains the text. Returns 'label | name | id' rows."""
        # ponytail: CONTAINS scan over all nodes, add full-text index per label when the graph grows
        return rows("MATCH (n) WHERE toLower(n.name) CONTAINS toLower($s) RETURN labels(n)[0], n.name, n.id LIMIT 10", {"s": name})

    @tool
    def neighbors(name: str) -> list:
        """List every relationship of the node with this exact name, as 'A -[REL]-> B' lines."""
        rows = q("""MATCH (n {name: $s})-[r]-(m)
                    RETURN type(r), startNode(r) = n, coalesce(m.name, m.question, m.text) LIMIT 50""", {"s": name})
        return [f"{name} -[{t}]-> {m}" if out else f"{m} -[{t}]-> {name}" for t, out, m in rows]

    @tool
    def decisions_for(name: str) -> list:
        """Decisions that changed concepts connected to a person, concept or decision whose name contains the text.
        Returns the graph path, reason, proposer, approver and source doc."""
        rows = q("""MATCH (n) WHERE toLower(n.name) CONTAINS toLower($s)
                    MATCH p = (n)-[:MEMBER_OF|RELATES_TO|CHANGED*0..2]->(:Concept)<-[:CHANGED]-(d:Decision)
                    OPTIONAL MATCH (d)-[:PROPOSED_BY]->(pb) OPTIONAL MATCH (d)-[:APPROVED_BY]->(ab)
                    OPTIONAL MATCH (d)-[:DOCUMENTED_IN]->(doc)
                    RETURN DISTINCT d.name, d.date, d.reason, [v IN nodes(p) | v.name], pb.name, ab.name,
                           doc.name, doc.url, doc.summary""", {"s": name})
        return [{"decision": dec, "date": date, "reason": reason, "path": " -> ".join(path), "proposed_by": pb,
                 "approved_by": ab, "doc": {"title": doc, "url": url, "summary": summary}}
                for dec, date, reason, path, pb, ab, doc, url, summary in rows]

    @tool
    def impact_of(concept: str) -> list:
        """Everyone affected if a concept changes: 'concept | related concept | person | title | manager' rows."""
        return rows("""MATCH (x:Concept)<-[:RELATES_TO*0..2]-(pl:Concept)<-[:MEMBER_OF]-(p:Person) WHERE toLower(x.name) CONTAINS toLower($s)
                    OPTIONAL MATCH (p)-[:REPORTS_TO]->(m:Person)
                    RETURN x.name, pl.name, p.name, p.title, m.name""", {"s": concept})

    @tool
    def create_task(assignee: str, text: str) -> str:
        """Create a follow-up task in the graph for the person with this exact name (e.g. brief a team on a change)."""
        res = g.query("""MATCH (p:Person {name: $p})
                         CREATE (t:Task {text: $t, status: 'open', created: $ts})-[:ASSIGNED_TO]->(p) RETURN p.name""",
                      {"p": assignee, "t": text, "ts": datetime.now().isoformat(timespec="seconds")})
        return f"task created for {assignee}" if res.result_set else f"no person named {assignee}"

    @tool
    def find_stale_docs() -> list:
        """Docs that are out of date: a decision changed a concept they describe after they were last updated."""
        return stale_docs(g)

    @tool
    def search_past_chats(text: str) -> list:
        """Search earlier conversations for a topic or entity name: everyone's shared chats plus this user's private ones.
        Returns 'date | who | question | answer | shared/private' rows."""
        cond = "toLower(e.question + ' ' + e.answer) CONTAINS toLower($s) OR any(n IN e.about WHERE toLower(n) CONTAINS toLower($s))"
        return [" | ".join([ts, who, qn, ans[:600], tag]) for ts, who, qn, ans, tag in episodes(g, pg, user, cond, {"s": text})]

    @tool
    def search_docs(text: str) -> list:
        """Full-text search over the document text. Returns the best matching passages with doc title and url.
        Use for anything the structured tools don't cover, then follow up with find_entity/neighbors on what you find."""
        terms = " OR ".join(re.findall(r"\w+", text))
        if not terms:
            return []
        return rows("""CALL db.index.fulltext.queryNodes('chunk_text', $s) YIELD node, score
                       MATCH (node)-[:PART_OF]->(d:Doc) RETURN d.id, d.name, d.url, left(node.text, 1200) LIMIT 5""", {"s": terms})

    def doc_path(doc_id):
        found = q("MATCH (d:Doc {id: $id}) RETURN d.path", {"id": doc_id})
        path = Path(found[0][0]) if found and found[0][0] else None
        return path if path and path.is_file() else None

    @tool
    def read_file(doc_id: str, offset: int = 0) -> str:
        """Read the original file of a document (doc id from search_docs or find_entity), 8000 characters from offset.
        Use when the graph and search_docs passages are not enough to answer exactly."""
        path = doc_path(doc_id)
        if not path:
            return "no stored file for this document (it was added before files were kept); ask the user to upload it again"
        text = path.read_text(errors="ignore")
        return f"[{offset}-{min(offset + 8000, len(text))} of {len(text)} chars]\n{text[offset:offset + 8000]}"

    @tool
    def query_csv(doc_id: str, sql: str) -> str:
        """Run a read-only DuckDB SQL SELECT over a CSV document; the file is the table `data`. Use for exact counts, sums,
        filters and lookups instead of reading rows yourself. Returns up to 100 rows."""
        path = doc_path(doc_id)
        if not path:
            return "no stored file for this document (it was added before files were kept); ask the user to upload it again"
        con = duckdb.connect()
        try:
            con.execute("CREATE TABLE data AS SELECT * FROM read_csv_auto(?)", [str(path)])
            con.execute("SET enable_external_access = false")
            res = con.execute(sql)
            return "\n".join([" | ".join(c[0] for c in res.description)] + [" | ".join(map(str, r)) for r in res.fetchmany(100)])
        except Exception as e:
            cols = [r[0] for r in con.execute("DESCRIBE data").fetchall()] if con.execute("SELECT count(*) FROM duckdb_tables()").fetchone()[0] else []
            return f"error: {e}. Table `data` columns: {cols}"

    @tool
    def run_cypher(query: str) -> str:
        """Run a read-only Cypher query. Use only when no other tool fits."""
        try:
            return str(q(query)[:50])
        except Exception as e:
            return f"error: {e}. Fix the query using the schema and retry."

    return [find_entity, neighbors, decisions_for, impact_of, create_task, find_stale_docs, search_docs, read_file, query_csv, search_past_chats, run_cypher]


def stale_docs(g):
    rows = g.ro_query("""MATCH (doc:Doc)-[:ABOUT]->(r:Concept)<-[:CHANGED]-(d:Decision)
                         WHERE d.date > doc.updated
                         OPTIONAL MATCH (d)-[:DOCUMENTED_IN]->(own:Doc)
                         WITH doc, r, d, own WHERE own IS NULL OR own <> doc
                         OPTIONAL MATCH (r)<-[:RELATES_TO*0..2]-(:Concept)<-[:MEMBER_OF]-(p:Person)
                         OPTIONAL MATCH (d)-[:DOCUMENTED_IN]->(src:Doc)
                         RETURN doc.name, doc.url, doc.updated, r.name, r.value, d.name, d.date, src.name,
                                collect(DISTINCT p.name) ORDER BY d.date DESC""").result_set
    return [{"doc": doc, "url": url, "doc_updated": upd, "concept": concept, "current_value": val, "decision": dec,
             "decided": date, "decision_source": src, "people_reading_it": people}
            for doc, url, upd, concept, val, dec, date, src, people in rows]


def path_graph(g, text):
    """Nodes named in the text plus the decisions/docs linking them, for drawing the answer's path."""
    names = [r[0] for r in g.ro_query("""MATCH (n) WHERE (n:Person OR n:Concept OR n:Decision OR n:Doc)
                                         AND toLower($t) CONTAINS toLower(n.name) RETURN n.name""", {"t": text}).result_set]
    rows = g.ro_query("""MATCH (a)-[r]->(b) WHERE a.name IN $n OR b.name IN $n
                         RETURN labels(a)[0], a.name, type(r), labels(b)[0], b.name""", {"n": names}).result_set
    # keep edges between named nodes, plus bridge nodes (decision, doc) that touch 2+ named nodes
    labels = {a: la for la, a, _, _, _ in rows} | {b: lb for _, _, _, lb, b in rows}
    links = {}
    for _, a, _, _, b in rows:
        for x, other in ((a, b), (b, a)):
            if labels.get(x) in ("Decision", "Doc") and x not in names and other in names:
                links.setdefault(x, set()).add(other)
    keep = set(names) | {x for x, s in links.items() if len(s) >= 2}
    edges = [(a, r, b) for _, a, r, _, b in rows if a in keep and b in keep]
    return {n: labels.get(n, "") for n in keep}, edges


def llm(prompt):
    """One-shot completion: Anthropic API if a key is set, else local `claude -p`."""
    if os.getenv("ANTHROPIC_API_KEY"):
        return text_of(ChatAnthropic(model=MODEL, max_tokens=4000).invoke(prompt).content)
    out = subprocess.run(["claude", "-p", prompt, "--model", MODEL, "--tools", "", "--strict-mcp-config", "--output-format", "json"],
                         capture_output=True, text=True, timeout=180, cwd=HERE)
    return json.loads(out.stdout)["result"]


def private_name(tenant):
    return f"{tenant}-private"


def sessions(kg, pg, user):
    """The user's sessions from both stores, newest first, as (id, title, created, shared)."""
    rows = [[*r, shared] for g, shared in ((kg, True), (pg, False))
            for r in g.ro_query("""MATCH (:User {name: $u})-[:HAS_SESSION]->(s:Session)
                                   RETURN s.id, s.title, s.created""", {"u": user}).result_set]
    return sorted(rows, key=lambda r: r[2], reverse=True)[:20]


def session_history(g, sid, user=None):
    """Q&A pairs of a session in order. With a user, only if that user owns the session."""
    owner = "(:User {name: $u})-[:HAS_SESSION]->" if user else ""
    return g.ro_query(f"""MATCH {owner}(:Session {{id: $s}})-[:HAS_EPISODE]->(e:Episode)
                          RETURN e.question, e.answer ORDER BY e.ts""", {"s": sid, "u": user}).result_set


def delete_session(g, user, sid):
    g.query("""MATCH (:User {name: $u})-[:HAS_SESSION]->(s:Session {id: $s})
               OPTIONAL MATCH (s)-[:HAS_EPISODE]->(e) DETACH DELETE e, s""", {"u": user, "s": sid})


def episodes(kg, pg, user, cond="true", params=None, limit=5):
    """Shared episodes (everyone's, in the knowledge graph) plus this user's private ones, newest first."""
    rows = [[*r, tag] for g, who, tag in ((kg, "", "shared"), (pg, "{name: $u}", "private"))
            for r in g.ro_query(f"""MATCH (u:User {who})-[:ASKED]->(e:Episode) WHERE {cond}
                                    RETURN e.ts, u.name, e.question, e.answer ORDER BY e.ts DESC LIMIT {limit}""",
                                {"u": user, **(params or {})}).result_set]
    return sorted(rows, key=lambda r: r[0], reverse=True)[:limit]


def recall(kg, pg, user, session=None):
    """Latest episodes from other chats (the current one is already in the chat history)."""
    rows = episodes(kg, pg, user, "NOT EXISTS { (:Session {id: $s})-[:HAS_EPISODE]->(e) }", {"s": session})
    if not rows:
        return ""
    lines = "\n".join(f"- {ts} ({tag}, {who}): asked '{qn}' -> answered '{ans[:300]}'" for ts, who, qn, ans, tag in rows)
    return f"Most recent conversations in other chats, shared ones and {user}'s private ones (use search_past_chats for older ones):\n{lines}"


def remember(chat_g, kg, user, question, answer, session=None):
    """Store the Q&A in chat_g (the knowledge graph if the chat is shared, else the private graph)."""
    about = [r[0] for r in kg.ro_query("""MATCH (n) WHERE (n:Person OR n:Concept OR n:Decision OR n:Doc)
                                          AND toLower($t) CONTAINS toLower(n.name) RETURN n.name""",
                                       {"t": f"{question} {answer}"}).result_set]
    chat_g.query("""MERGE (u:User {name: $u})
                    CREATE (u)-[:ASKED]->(e:Episode {ts: $ts, question: $q, answer: $a, about: $about})
                    WITH u, e
                    FOREACH (sid IN CASE WHEN $s IS NULL THEN [] ELSE [$s] END |
                        MERGE (s:Session {id: sid}) ON CREATE SET s.created = $ts, s.title = left($q, 60)
                        MERGE (u)-[:HAS_SESSION]->(s) MERGE (s)-[:HAS_EPISODE]->(e))""",
                 {"u": user, "ts": datetime.now().isoformat(timespec="seconds"), "q": question, "a": answer,
                  "s": session, "about": about})


def run_langgraph(question, history, system, tenant, user):
    agent = create_react_agent(ChatAnthropic(model=MODEL, max_tokens=16000), make_tools(db.select_graph(tenant), user, db.select_graph(private_name(tenant))), prompt=system)
    msgs = agent.invoke({"messages": [*history, ("user", question)]})["messages"]
    steps = [(c["name"], c["args"]) for m in msgs if m.type == "ai" for c in m.tool_calls]
    return text_of(msgs[-1].content), steps


def run_claude_cli(question, history, system, tenant, user):
    # local testing without an API key: Claude Code (your subscription) drives the same tools over MCP
    mcp = {"mcpServers": {"lattice": {"command": "uv", "args": ["run", "--directory", HERE, "python", "mcp_server.py"],
                                        "env": {"TENANT": tenant, "USER_NAME": user}}}}
    convo = "".join(f"{role}: {text}\n" for role, text in history)
    prompt = f"Conversation so far:\n{convo}\nuser: {question}" if convo else question
    out = subprocess.run(
        ["claude", "-p", prompt, "--model", MODEL, "--system-prompt", system, "--mcp-config", json.dumps(mcp), "--strict-mcp-config",
         "--tools", "", "--allowedTools", "mcp__lattice", "--output-format", "stream-json", "--verbose"],
        capture_output=True, text=True, timeout=300, cwd=HERE,
    )
    events = [json.loads(line) for line in out.stdout.splitlines() if line.startswith("{")]
    steps = [(b["name"].removeprefix("mcp__lattice__"), b["input"])
             for e in events if e.get("type") == "assistant"
             for b in e["message"]["content"] if b.get("type") == "tool_use"]
    result = next((e for e in events if e.get("type") == "result"), {})
    return result.get("result") or f"claude -p failed: {out.stderr.strip()[-500:]}", steps


def ask(question, user="guest", tenant="default", history=(), session=None, shared=False):
    g = db.create_graph(tenant)
    pg = db.create_graph(private_name(tenant))
    run = run_langgraph if os.getenv("ANTHROPIC_API_KEY") else run_claude_cli
    answer, steps = run(question, list(history), SYSTEM.replace("{schema}", schema(g)).replace("{memory}", recall(g, pg, user, session)), tenant, user)
    remember(g if shared else pg, g, user, question, answer, session)
    return answer, steps


if __name__ == "__main__":
    import sys
    answer, steps = ask(" ".join(sys.argv[1:]) or "What decisions have been made and who approved them?")
    for name, args in steps:
        print(f"[tool] {name} {args}")
    print(answer)
