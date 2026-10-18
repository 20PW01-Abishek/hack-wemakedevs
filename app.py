import json
import textwrap

import streamlit as st

from agent import ask, db, path_graph, recall, stale_docs
from ingest import ingest_doc

COLORS = {"Person": "#f0abfc", "Team": "#fcd34d", "Plan": "#93c5fd", "Rule": "#f9a8d4", "Decision": "#86efac", "Doc": "#7dd3fc"}


def dot(nodes, edges):
    q = json.dumps
    lines = ['digraph { rankdir=LR; bgcolor="transparent"; node [shape=box, style="filled,rounded", fontname=Helvetica, fontsize=10];',
             'edge [fontname=Helvetica, fontsize=8, color="#888888", fontcolor="#888888"];']
    lines += [f'{q(n)} [label={q(textwrap.fill(n, 28) + chr(10) + "(" + l + ")")}, fillcolor="{COLORS.get(l, "#e5e7eb")}"];'
              for n, l in nodes.items()]
    lines += [f"{q(a)} -> {q(b)} [label={q(r)}];" for a, r, b in edges]
    return "\n".join(lines + ["}"])


st.set_page_config(page_title="Comp Brain", page_icon="🧠", layout="wide")

with st.sidebar:
    graphs = db.list_graphs() or ["acme"]
    tenant = st.selectbox("Tenant (one graph per tenant)", graphs, index=graphs.index("acme") if "acme" in graphs else 0)
    g = db.select_graph(tenant)
    people = [r[0] for r in g.ro_query("MATCH (p:Person) RETURN p.name ORDER BY p.name").result_set]
    user = st.selectbox("Asking as", people or ["guest"])

    with st.form("add_doc", clear_on_submit=True):
        st.markdown("**📄 Teach the brain: add a document**")
        title = st.text_input("Title", placeholder="Comp Committee Minutes Oct 18")
        author = st.selectbox("Author", people)
        body = st.text_area("Text", height=150, placeholder="Farhan proposed raising the SDR bonus to INR 2000 from Nov 1. Lakshmi approved.")
        if st.form_submit_button("Add to graph") and title and body:
            with st.spinner("Reading the document and updating the graph..."):
                learned = ingest_doc(g, title, author, body)
            st.success(f"Learned: {learned.get('summary', '')}")
            for d in learned.get("decisions") or []:
                st.info(f"New decision: {d['summary']} (approved by {d.get('approved_by') or 'unknown'})")

    st.markdown("**🧠 Memory from past sessions**")
    st.text(recall(g, user) or "nothing yet")
    st.markdown(f"[Open graph in FalkorDB Browser](http://localhost:3000/graph?graph={tenant})")

st.title("🧠 Comp Brain")
st.caption("Ask why comp rules changed, who decided, and who is affected. Every answer is a path through the FalkorDB graph.")

if alerts := stale_docs(g):
    with st.expander(f"⚠️ The brain found {len(alerts)} outdated document(s)", expanded=True):
        for a in alerts:
            st.warning(f"**{a['doc']}** (last updated {a['doc_updated']}) is out of date: on {a['decided']} "
                       f"*{a['decision']}*. **{a['rule']}** is now **{a['current_value']}**. "
                       f"{len(a['people_reading_it'])} people on affected plans: {', '.join(a['people_reading_it'])}.")

key = f"chat:{tenant}:{user}"
st.session_state.setdefault(key, [])
chat = st.session_state[key]


def show(answer, steps, graph):
    st.markdown(answer)
    if graph:
        st.graphviz_chart(graph)
    with st.expander(f"Graph tool calls ({len(steps)})"):
        for name, args in steps:
            st.code(f"{name}({args})")


for msg in chat:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            show(msg["text"], msg["steps"], msg["graph"])
        else:
            st.markdown(msg["text"])

if question := st.chat_input("Why did Priya's commission drop in Q3 and who approved it?"):
    st.chat_message("user").markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Walking the graph..."):
            answer, steps = ask(question, user=user, tenant=tenant, history=[(m["role"], m["text"]) for m in chat])
            path = answer.split("Path:", 1)[1].split("Sources:", 1)[0] if "Path:" in answer else answer
            nodes, edges = path_graph(g, path)
            graph = dot(nodes, edges) if edges else None
        show(answer, steps, graph)
    chat += [{"role": "user", "text": question}, {"role": "assistant", "text": answer, "steps": steps, "graph": graph}]
