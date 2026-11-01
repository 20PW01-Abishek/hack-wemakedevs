import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

from agent import db, llm

PROMPT = """You extract organisational knowledge from a document (or one part of a long one).
Known people: {people}
Known concepts (name: current value): {concepts}

Document "{title}" by {author} (part {part}):
{text}

Return ONLY a JSON object:
{{"summary": "one line summary of the document",
  "about": [names of concepts the document discusses],
  "people": [{{"name": "person mentioned", "title": "job title or null", "manager": "their manager's name or null"}}],
  "concepts": [{{"name": "a rule, plan, policy, product, project, team, process...", "kind": "what kind of thing it is",
                 "relates_to": [names of other concepts it is linked to], "members": [names of people involved in or part of it]}}],
  "decisions": [{{"summary": "one line, what changed (from -> to) and from when",
                  "date": "YYYY-MM-DD the decision was made",
                  "reason": "why, in one sentence",
                  "concept": "name of the concept that changed (a known one, or a short new name)",
                  "new_value": "the concept's value or state after the change",
                  "proposed_by": "person name or null",
                  "approved_by": "person name or null"}}]}}
Only include decisions that the document says were approved or decided."""


EXTS = {".md", ".txt", ".csv"}
UPLOADS = Path(os.getenv("UPLOADS_DIR", "uploads"))
CHUNK = 6000


def split(text, csv=False):
    """Split into ~CHUNK-char parts at line boundaries (markdown headings preferred); csv parts repeat the header."""
    lines = text.splitlines()
    header, lines = (lines[0], lines[1:]) if csv and lines else (None, lines)
    parts, cur, size = [], [], 0
    for line in lines:
        if cur and (size + len(line) > CHUNK or (line.startswith("#") and size > CHUNK // 2)):
            parts.append(cur)
            cur, size = [], 0
        cur.append(line)
        size += len(line) + 1
    parts.append(cur)
    return ["\n".join(([header] if header else []) + p) for p in parts if p]


def ingest_doc(g, title, author, text, doc_id=None, url=None, csv=False, path=None):
    """Keep the original file (uploads/ unless a path is given), add it in parts, let the LLM extract what each part discusses and decides, and MERGE it into the graph."""
    q = lambda c: g.ro_query(c).result_set
    doc_id = doc_id or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if path is None:
        UPLOADS.mkdir(parents=True, exist_ok=True)
        path = (UPLOADS / (doc_id + (".csv" if csv else ".md"))).resolve()
        path.write_text(text)
    g.query("MATCH (c:Chunk {doc: $id}) DETACH DELETE c", {"id": doc_id})
    g.query("""MERGE (d:Doc {id: $id}) SET d.name = $title, d.url = $url, d.path = $path, d.updated = $today
               WITH d FOREACH (a IN CASE WHEN $author IS NULL THEN [] ELSE [$author] END |
                               MERGE (p:Person {name: a}) MERGE (p)-[:AUTHORED]->(d))""",
            {"id": doc_id, "title": title, "url": url, "path": str(path), "author": author, "today": date.today().isoformat()})
    parts = split(text, csv)
    result = {"summary": "", "decisions": []}
    for j, part in enumerate(parts):
        out = json.loads((raw := llm(PROMPT.format(
            people=", ".join(r[0] for r in q("MATCH (p:Person) RETURN p.name")),
            concepts="; ".join(f"{n}: {v}" for n, v in q("MATCH (c:Concept) RETURN c.name, c.value")),
            title=title, author=author or "unknown", part=f"{j + 1}/{len(parts)}", text=part,
        )))[raw.find("{"): raw.rfind("}") + 1])
        result["summary"] = result["summary"] or out.get("summary", "")
        result["decisions"] += out.get("decisions") or []
        merge(g, doc_id, j, part, out)
    g.query("MATCH (d:Doc {id: $id}) SET d.summary = $s", {"id": doc_id, "s": result["summary"]})
    return result


def merge(g, doc_id, j, part, out):
    g.query("""MATCH (d:Doc {id: $doc}) CREATE (c:Chunk {id: $doc + '-' + $j, doc: $doc, text: $text})-[:PART_OF]->(d)
               WITH c, d UNWIND $about AS ab
               OPTIONAL MATCH (x) WHERE x:Concept AND x.name = ab
               FOREACH (t IN CASE WHEN x IS NULL THEN [] ELSE [x] END | MERGE (c)-[:ABOUT]->(t) MERGE (d)-[:ABOUT]->(t))""",
            {"doc": doc_id, "j": str(j), "text": part, "about": out.get("about") or []})
    g.query("""UNWIND $people AS p MERGE (x:Person {name: p.name}) SET x.title = coalesce(p.title, x.title)
               WITH x, p WHERE p.manager IS NOT NULL
               MERGE (m:Person {name: p.manager}) MERGE (x)-[:REPORTS_TO]->(m)""", {"people": out.get("people") or []})
    g.query("""UNWIND $concepts AS c MERGE (p:Concept {name: c.name}) SET p.kind = coalesce(c.kind, p.kind)
               WITH p, c
               FOREACH (r IN coalesce(c.relates_to, []) | MERGE (x:Concept {name: r}) MERGE (p)-[:RELATES_TO]->(x))
               FOREACH (m IN coalesce(c.members, []) | MERGE (x:Person {name: m}) MERGE (x)-[:MEMBER_OF]->(p))""",
            {"concepts": out.get("concepts") or []})
    for i, dec in enumerate(out.get("decisions") or []):
        g.query("""MATCH (doc:Doc {id: $doc})
                   MERGE (r:Concept {name: $d.concept}) SET r.value = $d.new_value
                   MERGE (dec:Decision {id: $id}) SET dec.name = $d.summary, dec.date = $d.date, dec.reason = $d.reason
                   MERGE (dec)-[:CHANGED]->(r) MERGE (dec)-[:DOCUMENTED_IN]->(doc) MERGE (doc)-[:ABOUT]->(r)
                   WITH dec
                   FOREACH (n IN CASE WHEN $d.proposed_by IS NULL THEN [] ELSE [$d.proposed_by] END |
                            MERGE (x:Person {name: n}) MERGE (dec)-[:PROPOSED_BY]->(x))
                   FOREACH (n IN CASE WHEN $d.approved_by IS NULL THEN [] ELSE [$d.approved_by] END |
                            MERGE (x:Person {name: n}) MERGE (dec)-[:APPROVED_BY]->(x))""",
                {"doc": doc_id, "id": f"{doc_id}-{j}-{i}", "d": dec})


def ingest_folder(g, root=None, progress=print):
    """Ingest every .md/.txt/.csv under root (recursively). Files whose content hash is unchanged are skipped."""
    root = Path(root or os.getenv("DOCS_DIR", "documentation"))
    done = 0
    for path in sorted(p for p in root.rglob("*") if p.suffix.lower() in EXTS and p.is_file()):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(errors="ignore")
        digest = hashlib.sha1(text.encode()).hexdigest()
        doc_id = re.sub(r"[^a-z0-9]+", "-", rel.lower()).strip("-")
        old = g.ro_query("MATCH (d:Doc {id: $id}) RETURN d.hash", {"id": doc_id}).result_set
        if old and old[0][0] == digest:
            continue
        progress(f"ingesting {rel}")
        ingest_doc(g, rel, None, text, doc_id=doc_id, url=rel, csv=path.suffix.lower() == ".csv", path=path.resolve())
        g.query("MATCH (d:Doc {id: $id}) SET d.hash = $h", {"id": doc_id, "h": digest})
        done += 1
    return done


def list_documents(g):
    rows = g.ro_query("""MATCH (d:Doc) OPTIONAL MATCH (c:Chunk)-[:PART_OF]->(d)
                         RETURN d.id, d.name, d.url, d.updated, d.summary, count(c)
                         ORDER BY d.updated DESC, d.name""").result_set
    return [{"id": i, "name": n, "url": u, "updated": up, "summary": s, "chunks": c} for i, n, u, up, s, c in rows]


def delete_document(g, doc_id):
    """Remove a document with its text chunks, the decisions it recorded and its uploaded file."""
    old = g.ro_query("MATCH (d:Doc {id: $id}) RETURN d.path", {"id": doc_id}).result_set
    if old and old[0][0] and Path(old[0][0]).is_relative_to(UPLOADS.resolve()):
        Path(old[0][0]).unlink(missing_ok=True)
    g.query("MATCH (c:Chunk)-[:PART_OF]->(:Doc {id: $id}) DETACH DELETE c", {"id": doc_id})
    g.query("MATCH (x:Decision)-[:DOCUMENTED_IN]->(:Doc {id: $id}) DETACH DELETE x", {"id": doc_id})
    g.query("MATCH (d:Doc {id: $id}) DETACH DELETE d", {"id": doc_id})


if __name__ == "__main__":
    if sys.argv[1] == "--folder":
        print(f"{ingest_folder(db.create_graph(sys.argv[2] if len(sys.argv) > 2 else 'default'))} files ingested")
    else:
        tenant = sys.argv[4] if len(sys.argv) > 4 else "default"
        print(json.dumps(ingest_doc(db.create_graph(tenant), sys.argv[1], sys.argv[2], sys.argv[3]), indent=1))
