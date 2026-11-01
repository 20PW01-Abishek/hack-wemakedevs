"use client";

import { useState } from "react";
import { useUserStore } from "@/domain/userStore";

/** Create an account with a role. */
export default function UserForm() {
  const add = useUserStore((s) => s.add);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [admin, setAdmin] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (await add({ username, password, admin })) {
      setUsername("");
      setPassword("");
      setAdmin(false);
    }
  }

  return (
    <form className="card row" onSubmit={submit}>
      <input placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="off" />
      <input
        type="password"
        placeholder="Password (8+ characters)"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        autoComplete="new-password"
      />
      <select value={admin ? "admin" : "member"} onChange={(e) => setAdmin(e.target.value === "admin")}>
        <option value="member">Member</option>
        <option value="admin">Admin</option>
      </select>
      <button className="primary" disabled={!username || !password}>
        Add user
      </button>
    </form>
  );
}
