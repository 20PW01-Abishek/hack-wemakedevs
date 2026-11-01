"use client";

import { useAuthStore } from "@/domain/authStore";
import { useUserStore } from "@/domain/userStore";
import Icon from "./Icon";

/** All accounts, with role changes and deletion. */
export default function UserTable() {
  const me = useAuthStore((s) => s.account?.user);
  const { users, setAdmin, remove } = useUserStore();

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>User</th>
            <th>Role</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.username}>
              <td>
                <span className="avatar small-avatar">{u.username.slice(0, 1).toUpperCase()}</span>
                <strong>{u.username}</strong>
                {u.username === me && <span className="muted small"> (you)</span>}
              </td>
              <td>
                <select value={u.admin ? "admin" : "member"} onChange={(e) => setAdmin(u.username, e.target.value === "admin")}>
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                </select>
              </td>
              <td>
                <button
                  className="icon-button"
                  disabled={u.username === me}
                  aria-label={`Delete ${u.username}`}
                  title={u.username === me ? "You cannot delete yourself" : "Delete this user and their private chats"}
                  onClick={() => window.confirm(`Delete ${u.username} and their private chats?`) && remove(u.username)}
                >
                  <Icon name="trash" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
