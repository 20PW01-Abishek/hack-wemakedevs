import json
import sys

from falkordb import FalkorDB

QUERIES = [
    ("teams", "UNWIND $rows AS r MERGE (:Team {name: r.name})"),
    ("people", """
        UNWIND $rows AS r
        MERGE (p:Person {id: r.id}) SET p.name = r.name, p.email = r.email, p.title = r.title
        WITH p, r MATCH (t:Team {name: r.team}) MERGE (p)-[:IN_TEAM]->(t)"""),
    ("people", """
        UNWIND $rows AS r
        MATCH (p:Person {id: r.id}), (m:Person {id: r.manager}) MERGE (p)-[:REPORTS_TO]->(m)"""),
    ("rules", "UNWIND $rows AS r MERGE (x:Rule {name: r.name}) SET x.value = r.value"),
    ("plans", """
        UNWIND $rows AS r
        MERGE (pl:Plan {id: r.id}) SET pl.name = r.name
        WITH pl, r UNWIND r.members AS mid MATCH (p:Person {id: mid}) MERGE (p)-[:ON_PLAN]->(pl)"""),
    ("plans", """
        UNWIND $rows AS r
        MATCH (pl:Plan {id: r.id}) UNWIND r.rules AS rn MATCH (x:Rule {name: rn}) MERGE (pl)-[:USES]->(x)"""),
    ("docs", """
        UNWIND $rows AS r
        MERGE (d:Doc {id: r.id}) SET d.name = r.title, d.url = r.url, d.summary = r.summary, d.updated = r.updated
        WITH d, r MATCH (a:Person {id: r.author}) MERGE (a)-[:AUTHORED]->(d)
        WITH d, r UNWIND r.about AS ab MATCH (x) WHERE (x:Rule OR x:Plan) AND x.name = ab MERGE (d)-[:ABOUT]->(x)"""),
    ("decisions", """
        UNWIND $rows AS r
        MERGE (dec:Decision {id: r.id}) SET dec.name = r.summary, dec.date = r.date, dec.reason = r.reason
        WITH dec, r
        MATCH (x:Rule {name: r.changed}), (pb:Person {id: r.proposed_by}),
              (ab:Person {id: r.approved_by}), (d:Doc {id: r.doc})
        MERGE (dec)-[:CHANGED]->(x) MERGE (dec)-[:PROPOSED_BY]->(pb)
        MERGE (dec)-[:APPROVED_BY]->(ab) MERGE (dec)-[:DOCUMENTED_IN]->(d)"""),
]


def seed(graph="acme", path="data/company.json"):
    data = json.load(open(path))
    db = FalkorDB()
    if graph in db.list_graphs():
        db.select_graph(graph).delete()
    g = db.select_graph(graph)
    for key, q in QUERIES:
        g.query(q, {"rows": data[key]})
    nodes = g.query("MATCH (n) RETURN count(n)").result_set[0][0]
    edges = g.query("MATCH ()-[e]->() RETURN count(e)").result_set[0][0]
    print(f"seeded graph '{graph}': {nodes} nodes, {edges} edges")


if __name__ == "__main__":
    seed(*sys.argv[1:])
