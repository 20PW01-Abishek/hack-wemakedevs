import getpass
import hashlib
import hmac
import os
import sys

from agent import db, private_name


def _hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1).hex()


def has_users(g):
    return bool(g.ro_query("MATCH (u:User) WHERE u.hash IS NOT NULL RETURN 1 LIMIT 1").result_set)


def create_user(g, name, password, admin=False):
    if not name.strip() or len(password) < 8:
        raise ValueError("username required and password must be at least 8 characters")
    if g.ro_query("MATCH (u:User {name: $n}) WHERE u.hash IS NOT NULL RETURN 1", {"n": name}).result_set:
        raise ValueError("username already taken")
    salt = os.urandom(16)
    g.query("MERGE (u:User {name: $n}) SET u.hash = $h, u.salt = $s, u.admin = $a",
            {"n": name, "h": _hash(password, salt), "s": salt.hex(), "a": admin})


def check_user(g, name, password):
    """Returns {"admin": bool} for valid credentials, else None."""
    rows = g.ro_query("MATCH (u:User {name: $n}) WHERE u.hash IS NOT NULL RETURN u.hash, u.salt, u.admin", {"n": name}).result_set
    if not rows:
        _hash(password, bytes(16))
        return None
    h, salt, admin = rows[0]
    return {"admin": bool(admin)} if hmac.compare_digest(h, _hash(password, bytes.fromhex(salt))) else None


def get_user(g, name):
    """Returns {"admin": bool} if the account exists, else None."""
    rows = g.ro_query("MATCH (u:User {name: $n}) WHERE u.hash IS NOT NULL RETURN u.admin", {"n": name}).result_set
    return {"admin": bool(rows[0][0])} if rows else None


def list_users(g):
    rows = g.ro_query("MATCH (u:User) WHERE u.hash IS NOT NULL RETURN u.name, u.admin ORDER BY u.name").result_set
    return [{"username": name, "admin": bool(admin)} for name, admin in rows]


def set_admin(g, name, admin):
    g.query("MATCH (u:User {name: $n}) WHERE u.hash IS NOT NULL SET u.admin = $a", {"n": name, "a": admin})


def delete_user(g, name):
    """Remove the account together with its private chats."""
    g.query("""MATCH (u:User {name: $n}) WHERE u.hash IS NOT NULL
               OPTIONAL MATCH (u)-[:HAS_SESSION]->(s:Session)
               OPTIONAL MATCH (s)-[:HAS_EPISODE]->(e:Episode)
               DETACH DELETE e, s, u""", {"n": name})


if __name__ == "__main__":
    # uv run python auth.py <tenant> <username> [--admin]
    db.create_graph(sys.argv[1])
    g = db.create_graph(private_name(sys.argv[1]))
    create_user(g, sys.argv[2], getpass.getpass("Password: "), "--admin" in sys.argv)
    print("user created")
