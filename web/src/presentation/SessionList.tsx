"use client";

import { usePathname, useRouter } from "next/navigation";
import { useChatStore } from "@/domain/chatStore";
import type { ChatSession } from "@/domain/types";
import Icon from "./Icon";

/** The user's chats, newest first, in a scrolling list. Click one to open it. */
export default function SessionList() {
  const { sessions, activeId, openSession, removeSession } = useChatStore();
  const pathname = usePathname();
  const router = useRouter();

  async function open(session: ChatSession) {
    if (pathname !== "/") router.push("/");
    await openSession(session);
  }

  function remove(session: ChatSession) {
    if (window.confirm(`Delete "${session.title}"?`)) removeSession(session);
  }

  return (
    <div className="sessions">
      <p className="section-label">Chats</p>
      {sessions.length === 0 && <p className="muted small pad">No chats yet.</p>}
      <ul>
        {sessions.map((s) => (
          <li key={s.id} className={pathname === "/" && s.id === activeId ? "active" : ""}>
            <button className="open" onClick={() => open(s)} title={s.title}>
              <Icon name={s.shared ? "globe" : "lock"} size={14} />
              <span>{s.title}</span>
            </button>
            <button className="delete" onClick={() => remove(s)} aria-label={`Delete ${s.title}`} title="Delete this chat">
              <Icon name="trash" size={14} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
