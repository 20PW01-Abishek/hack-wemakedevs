import base64
import hashlib
import hmac
import json
import os
import secrets
import shutil
import time
from uuid import uuid4

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel

from agent import ask, db, delete_session, path_graph, private_name, session_history, sessions, stale_docs
from auth import check_user, create_user, delete_user, get_user, has_users, list_users, set_admin
from ingest import delete_document, ingest_doc, ingest_folder, list_documents

TENANT = os.getenv("TENANT", "default")
SECRET = os.getenv("SECRET_KEY") or secrets.token_hex(32)
COOKIE = "brain_session"
TTL = 7 * 24 * 3600

kg = db.create_graph(TENANT)
pg = db.create_graph(private_name(TENANT))
app = FastAPI(title="Lattice")


class Credentials(BaseModel):
    username: str
    password: str


class NewUser(Credentials):
    admin: bool = False


class RoleUpdate(BaseModel):
    admin: bool


class ChatRequest(BaseModel):
    question: str
    session: str | None = None
    shared: bool = False


class DocumentRequest(BaseModel):
    title: str
    author: str | None = None
    text: str


def sign(payload):
    """Encode a payload as a tamper-proof token."""
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return f"{body}.{hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()}"


def verify(token):
    """Return the token's payload, or None if it is forged or expired."""
    body, _, mac = token.rpartition(".")
    expected = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        return None
    payload = json.loads(base64.urlsafe_b64decode(body))
    return payload if payload["exp"] > time.time() else None


def login_cookie(response, username, admin):
    token = sign({"user": username, "admin": admin, "exp": time.time() + TTL})
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", max_age=TTL)


def current_user(brain_session: str | None = Cookie(None)):
    payload = verify(brain_session) if brain_session else None
    account = get_user(pg, payload["user"]) if payload else None
    if not account:
        raise HTTPException(401, "Not signed in")
    return {"user": payload["user"], **account}


def admin_user(user=Depends(current_user)):
    if not user["admin"]:
        raise HTTPException(403, "Admins only")
    return user


def graph_json(answer):
    path = answer.split("Path:", 1)[1].split("Sources:", 1)[0] if "Path:" in answer else answer
    nodes, edges = path_graph(kg, path)
    if not edges:
        return None
    return {"nodes": [{"id": n, "label": label} for n, label in nodes.items()],
            "edges": [{"from": a, "type": r, "to": b} for a, r, b in edges]}


def chat_graph(shared):
    return kg if shared else pg


@app.get("/status")
def status():
    """Whether the first admin account still has to be created."""
    return {"needs_setup": not has_users(pg)}


@app.post("/setup")
def setup(body: Credentials, response: Response):
    """Create the first admin account and sign in."""
    if has_users(pg):
        raise HTTPException(409, "Already set up")
    try:
        create_user(pg, body.username, body.password, admin=True)
    except ValueError as e:
        raise HTTPException(400, str(e))
    login_cookie(response, body.username, True)
    return {"user": body.username, "admin": True}


@app.post("/signup")
def signup(body: Credentials, response: Response):
    """Self-service sign up: creates a member account and signs in."""
    try:
        create_user(pg, body.username, body.password, admin=False)
    except ValueError as e:
        raise HTTPException(400, str(e))
    login_cookie(response, body.username, False)
    return {"user": body.username, "admin": False}


@app.post("/login")
def login(body: Credentials, response: Response):
    info = check_user(pg, body.username, body.password)
    if not info:
        raise HTTPException(401, "Wrong username or password")
    login_cookie(response, body.username, info["admin"])
    return {"user": body.username, **info}


@app.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/me")
def me(user=Depends(current_user)):
    return {"user": user["user"], "admin": user["admin"]}


@app.post("/users")
def add_user(body: NewUser, _=Depends(admin_user)):
    """Create another account (admins only)."""
    try:
        create_user(pg, body.username, body.password, body.admin)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.get("/users")
def users(_=Depends(admin_user)):
    return list_users(pg)


def guard_last_admin(username):
    admins = [u["username"] for u in list_users(pg) if u["admin"]]
    if admins == [username]:
        raise HTTPException(400, "There must be at least one admin")


@app.patch("/users/{username}")
def update_role(username: str, body: RoleUpdate, _=Depends(admin_user)):
    if not body.admin:
        guard_last_admin(username)
    set_admin(pg, username, body.admin)
    return {"ok": True}


@app.delete("/users/{username}")
def remove_user(username: str, user=Depends(admin_user)):
    """Delete an account and its private chats (admins only, never yourself or the last admin)."""
    if username == user["user"]:
        raise HTTPException(400, "You cannot delete yourself")
    guard_last_admin(username)
    delete_user(pg, username)
    return {"ok": True}


@app.get("/sessions")
def list_sessions(user=Depends(current_user)):
    return [{"id": sid, "title": title, "created": created, "shared": shared}
            for sid, title, created, shared in sessions(kg, pg, user["user"])]


@app.get("/sessions/{sid}")
def get_session(sid: str, shared: bool = False, user=Depends(current_user)):
    """Messages of one of the user's sessions, with the answer path graph."""
    rows = session_history(chat_graph(shared), sid, user["user"])
    return [m for q, a in rows
            for m in ({"role": "user", "text": q}, {"role": "assistant", "text": a, "steps": [], "graph": graph_json(a)})]


@app.delete("/sessions/{sid}")
def remove_session(sid: str, shared: bool = False, user=Depends(current_user)):
    delete_session(chat_graph(shared), user["user"], sid)
    return {"ok": True}


@app.post("/chat")
def chat(body: ChatRequest, user=Depends(current_user)):
    """Ask the agent. A new session id is created when none is given."""
    sid = body.session or uuid4().hex
    history = [(role, text) for q, a in session_history(chat_graph(body.shared), sid, user["user"])
               for role, text in (("user", q), ("assistant", a))]
    owned = pg.ro_query("""MATCH (s:Session {id: $s}) OPTIONAL MATCH (:User {name: $u})-[r:HAS_SESSION]->(s)
                           RETURN count(s), count(r)""", {"s": sid, "u": user["user"]}).result_set[0]
    if not body.shared and owned[0] and not owned[1]:
        raise HTTPException(403, "Not your session")
    if not os.getenv("ANTHROPIC_API_KEY") and not shutil.which("claude"):
        raise HTTPException(503, "ANTHROPIC_API_KEY is not set. Add it to vars.sh and restart the backend")
    answer, steps = ask(body.question, user=user["user"], tenant=TENANT, history=history, session=sid, shared=body.shared)
    return {"session": sid, "answer": answer, "steps": [{"name": n, "args": a} for n, a in steps], "graph": graph_json(answer)}


@app.get("/alerts")
def alerts(_=Depends(current_user)):
    """Documents that newer decisions have made outdated."""
    return stale_docs(kg)


@app.get("/documents")
def documents(_=Depends(current_user)):
    return list_documents(kg)


@app.post("/documents")
def add_document(body: DocumentRequest, user=Depends(current_user)):
    """Let the LLM read a document and merge what it learns into the graph."""
    return ingest_doc(kg, body.title, body.author or user["user"], body.text, csv=body.title.lower().endswith(".csv"))


@app.delete("/documents/{doc_id}")
def remove_document(doc_id: str, _=Depends(admin_user)):
    delete_document(kg, doc_id)
    return {"ok": True}


@app.post("/documents/sync")
def sync_documents(_=Depends(admin_user)):
    """Ingest new or changed files from the documentation folder."""
    return {"ingested": ingest_folder(kg, progress=lambda _: None)}
