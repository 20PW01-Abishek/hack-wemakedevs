"use client";

import { useEffect, useRef, useState } from "react";
import { useAuthStore } from "@/domain/authStore";
import Icon from "./Icon";

/** The signed-in user at the bottom of the sidebar. Click to reveal the log out action. */
export default function UserMenu({ collapsed }: { collapsed: boolean }) {
  const { account, logout } = useAuthStore();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function close(e: MouseEvent) {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  if (!account) return null;

  return (
    <div className="user-menu" ref={box}>
      {open && (
        <div className="popover" role="menu">
          <button role="menuitem" onClick={logout}>
            <Icon name="logout" />
            <span>Log out</span>
          </button>
        </div>
      )}
      <button className="user-button" onClick={() => setOpen(!open)} aria-expanded={open} title={account.user}>
        <span className="avatar">{account.user.slice(0, 1).toUpperCase()}</span>
        {!collapsed && (
          <>
            <span className="user-text">
              <strong>{account.user}</strong>
              <span className="muted small">{account.admin ? "Admin" : "Member"}</span>
            </span>
            <Icon name="chevron" size={16} />
          </>
        )}
      </button>
    </div>
  );
}
