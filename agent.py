import json
import os
import subprocess
from datetime import datetime

from dotenv import load_dotenv
from falkordb import FalkorDB
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

load_dotenv()
MODEL = os.getenv("MODEL", "claude-opus-5-5")
HERE = os.path.dirname(os.path.abspath(__file__))
db = FalkorDB(host=os.getenv("FALKORDB_HOST", "localhost"), port=int(os.getenv("FALKORDB_PORT", "6379")))

SYSTEM = """You are Comp Brain, a company knowledge agent for sales compensation.
All company knowledge lives in a FalkorDB graph. Answer only from what the tools return; never invent facts.

Graph schema (read live from the graph):
{schema}

How to answer:
- Start with find_entity to resolve names. If several match, pick from context or ask which one.
- For "why/who decided/what changed" questions use decisions_for.
- For "who is affected if X changes" use impact_of.
- For "is our documentation up to date / what is outdated" use find_stale_docs. When you notice a doc that contradicts a newer decision, warn the user.
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


def make_tools(g):
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
        """Decisions that changed rules affecting a person, plan, rule or decision whose name contains the text.
        Returns the graph path, reason, proposer, approver and source doc."""
        rows = q("""MATCH (n) WHERE toLower(n.name) CONTAINS toLower($s)
                    MATCH p = (n)-[:ON_PLAN|USES|CHANGED*0..2]->(:Rule)<-[:CHANGED]-(d:Decision)
                    OPTIONAL MATCH (d)-[:PROPOSED_BY]->(pb) OPTIONAL MATCH (d)-[:APPROVED_BY]->(ab)
                    OPTIONAL MATCH (d)-[:DOCUMENTED_IN]->(doc)
                    RETURN DISTINCT d.name, d.date, d.reason, [v IN nodes(p) | v.name], pb.name, ab.name,
                           doc.name, doc.url, doc.summary""", {"s": name})
        return [{"decision": dec, "date": date, "reason": reason, "path": " -> ".join(path), "proposed_by": pb,
                 "approved_by": ab, "doc": {"title": doc, "url": url, "summary": summary}}
                for dec, date, reason, path, pb, ab, doc, url, summary in rows]

    @tool
    def impact_of(rule: str) -> list:
        """Everyone affected if a rule changes: 'rule | plan | person | title | manager' rows."""
        return rows("""MATCH (x:Rule)<-[:USES]-(pl:Plan)<-[:ON_PLAN]-(p:Person) WHERE toLower(x.name) CONTAINS toLower($s)
                    OPTIONAL MATCH (p)-[:REPORTS_TO]->(m:Person)
                    RETURN x.name, pl.name, p.name, p.title, m.name""", {"s": rule})

    @tool
    def create_task(assignee: str, text: str) -> str:
        """Create a follow-up task in the graph for the person with this exact name (e.g. brief a team on a rule change)."""
        res = g.query("""MATCH (p:Person {name: $p})
                         CREATE (t:Task {text: $t, status: 'open', created: $ts})-[:ASSIGNED_TO]->(p) RETURN p.name""",
                      {"p": assignee, "t": text, "ts": datetime.now().isoformat(timespec="seconds")})
        return f"task created for {assignee}" if res.result_set else f"no person named {assignee}"

    @tool
    def find_stale_docs() -> list:
        """Docs that are out of date: a decision changed a rule they describe after they were last updated."""
        return stale_docs(g)

    @tool
    def run_cypher(query: str) -> str:
        """Run a read-only Cypher query. Use only when no other tool fits."""
        try:
            return str(q(query)[:50])
        except Exception as e:
            return f"error: {e}. Fix the query using the schema and retry."

    return [find_entity, neighbors, decisions_for, impact_of, create_task, find_stale_docs, run_cypher]


def stale_docs(g):
    rows = g.ro_query("""MATCH (doc:Doc)-[:ABOUT]->(r:Rule)<-[:CHANGED]-(d:Decision)
                         WHERE d.date > doc.updated
                         OPTIONAL MATCH (d)-[:DOCUMENTED_IN]->(own:Doc)
                         WITH doc, r, d, own WHERE own IS NULL OR id(own) <> id(doc)
                         OPTIONAL MATCH (r)<-[:USES]-(:Plan)<-[:ON_PLAN]-(p:Person)
                         OPTIONAL MATCH (d)-[:DOCUMENTED_IN]->(src:Doc)
                         RETURN doc.name, doc.url, doc.updated, r.name, r.value, d.name, d.date, src.name,
                                collect(DISTINCT p.name) ORDER BY d.date DESC""").result_set
    return [{"doc": doc, "url": url, "doc_updated": upd, "rule": rule, "current_value": val, "decision": dec,
             "decided": date, "decision_source": src, "people_reading_it": people}
            for doc, url, upd, rule, val, dec, date, src, people in rows]


def path_graph(g, text):
    """Nodes named in the text plus the decisions/docs linking them, for drawing the answer's path."""
    names = [r[0] for r in g.ro_query("""MATCH (n) WHERE (n:Person OR n:Plan OR n:Rule OR n:Decision OR n:Doc OR n:Team)
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
    out = subprocess.run(["claude", "-p", prompt, "--tools", "", "--strict-mcp-config", "--output-format", "json"],
                         capture_output=True, text=True, timeout=180, cwd=HERE)
    return json.loads(out.stdout)["result"]


def recall(g, user):
    rows = g.ro_query("""MATCH (:User {name: $u})-[:ASKED]->(e:Episode)
                         RETURN e.ts, e.question, e.answer ORDER BY e.ts DESC LIMIT 5""", {"u": user}).result_set
    if not rows:
        return ""
    lines = "\n".join(f"- {ts}: asked '{qn}' -> answered '{ans[:300]}'" for ts, qn, ans in rows)
    return f"Memory of past sessions with {user} (most recent first):\n{lines}"


def remember(g, user, question, answer):
    g.query("""MERGE (u:User {name: $u})
               CREATE (u)-[:ASKED]->(e:Episode {ts: $ts, question: $q, answer: $a})
               WITH e MATCH (n) WHERE (n:Person OR n:Plan OR n:Rule OR n:Decision OR n:Doc)
                                  AND toLower($u + ' ' + $q + ' ' + $a) CONTAINS toLower(n.name)
               MERGE (e)-[:ABOUT]->(n)""",
            {"u": user, "ts": datetime.now().isoformat(timespec="seconds"), "q": question, "a": answer})


def run_langgraph(question, history, system, tenant):
    agent = create_react_agent(ChatAnthropic(model=MODEL, max_tokens=16000), make_tools(db.select_graph(tenant)), prompt=system)
    msgs = agent.invoke({"messages": [*history, ("user", question)]})["messages"]
    steps = [(c["name"], c["args"]) for m in msgs if m.type == "ai" for c in m.tool_calls]
    return text_of(msgs[-1].content), steps


def run_claude_cli(question, history, system, tenant):
    # local testing without an API key: Claude Code (your subscription) drives the same tools over MCP
    mcp = {"mcpServers": {"compbrain": {"command": "uv", "args": ["run", "--directory", HERE, "python", "mcp_server.py"],
                                        "env": {"TENANT": tenant}}}}
    convo = "".join(f"{role}: {text}\n" for role, text in history)
    prompt = f"Conversation so far:\n{convo}\nuser: {question}" if convo else question
    out = subprocess.run(
        ["claude", "-p", prompt, "--system-prompt", system, "--mcp-config", json.dumps(mcp), "--strict-mcp-config",
         "--tools", "", "--allowedTools", "mcp__compbrain", "--output-format", "stream-json", "--verbose"],
        capture_output=True, text=True, timeout=300, cwd=HERE,
    )
    events = [json.loads(line) for line in out.stdout.splitlines() if line.startswith("{")]
    steps = [(b["name"].removeprefix("mcp__compbrain__"), b["input"])
             for e in events if e.get("type") == "assistant"
             for b in e["message"]["content"] if b.get("type") == "tool_use"]
    result = next((e for e in events if e.get("type") == "result"), {})
    return result.get("result") or f"claude -p failed: {out.stderr.strip()[-500:]}", steps


def ask(question, user="guest", tenant="acme", history=()):
    g = db.select_graph(tenant)
    run = run_langgraph if os.getenv("ANTHROPIC_API_KEY") else run_claude_cli
    answer, steps = run(question, list(history), SYSTEM.replace("{schema}", schema(g)).replace("{memory}", recall(g, user)), tenant)
    remember(g, user, question, answer)
    return answer, steps


if __name__ == "__main__":
    import sys
    answer, steps = ask(" ".join(sys.argv[1:]) or "Why did Priya's commission drop in Q3 and who approved it?", user="Priya Sharma")
    for name, args in steps:
        print(f"[tool] {name} {args}")
    print(answer)
