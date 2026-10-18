import json
import re
import sys
from datetime import date

from agent import db, llm

PROMPT = """You extract compensation knowledge from a company document.
Known people: {people}
Known rules (name: current value): {rules}
Known plans: {plans}

Document "{title}" by {author}:
{text}

Return ONLY a JSON object:
{{"summary": "one line summary of the document",
  "about": [names of known rules or plans the document discusses],
  "decisions": [{{"summary": "one line, what changed (from -> to) and from when",
                  "date": "YYYY-MM-DD the decision was made",
                  "reason": "why, in one sentence",
                  "rule": "rule name (a known one, or a new short name if it is a new rule)",
                  "new_value": "the rule's value after the change",
                  "proposed_by": "known person name or null",
                  "approved_by": "known person name or null"}}]}}
Only include decisions that the document says were approved or decided."""


def ingest_doc(g, title, author, text):
    """Add a document, let the LLM extract what it discusses and decides, and MERGE that into the graph."""
    q = lambda c: g.ro_query(c).result_set
    out = json.loads((raw := llm(PROMPT.format(
        people=", ".join(r[0] for r in q("MATCH (p:Person) RETURN p.name")),
        rules="; ".join(f"{n}: {v}" for n, v in q("MATCH (r:Rule) RETURN r.name, r.value")),
        plans=", ".join(r[0] for r in q("MATCH (p:Plan) RETURN p.name")),
        title=title, author=author, text=text,
    )))[raw.find("{"): raw.rfind("}") + 1])
    doc_id = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    g.query("""MERGE (d:Doc {id: $id})
               SET d.name = $title, d.url = 'https://docs.acme.io/' + $id, d.summary = $summary, d.text = $text, d.updated = $today
               WITH d OPTIONAL MATCH (a:Person {name: $author})
               FOREACH (x IN CASE WHEN a IS NULL THEN [] ELSE [a] END | MERGE (x)-[:AUTHORED]->(d))
               WITH d UNWIND $about AS ab MATCH (x) WHERE (x:Rule OR x:Plan) AND x.name = ab MERGE (d)-[:ABOUT]->(x)""",
            {"id": doc_id, "title": title, "summary": out.get("summary", ""), "text": text, "author": author,
             "today": date.today().isoformat(), "about": out.get("about") or []})
    for i, dec in enumerate(out.get("decisions") or []):
        g.query("""MATCH (doc:Doc {id: $doc})
                   MERGE (r:Rule {name: $d.rule}) SET r.value = $d.new_value
                   MERGE (dec:Decision {id: $doc + '-' + $i}) SET dec.name = $d.summary, dec.date = $d.date, dec.reason = $d.reason
                   MERGE (dec)-[:CHANGED]->(r) MERGE (dec)-[:DOCUMENTED_IN]->(doc) MERGE (doc)-[:ABOUT]->(r)
                   WITH dec
                   OPTIONAL MATCH (pb:Person {name: $d.proposed_by})
                   OPTIONAL MATCH (ab:Person {name: $d.approved_by})
                   FOREACH (x IN CASE WHEN pb IS NULL THEN [] ELSE [pb] END | MERGE (dec)-[:PROPOSED_BY]->(x))
                   FOREACH (x IN CASE WHEN ab IS NULL THEN [] ELSE [ab] END | MERGE (dec)-[:APPROVED_BY]->(x))""",
                {"doc": doc_id, "i": str(i), "d": dec})
    return out


if __name__ == "__main__":
    print(json.dumps(ingest_doc(db.select_graph("acme"), sys.argv[1], sys.argv[2], sys.argv[3]), indent=1))
