"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/domain/authStore";
import { useChatStore } from "@/domain/chatStore";
import { useUiStore } from "@/domain/uiStore";
import Icon, { type IconName } from "./Icon";
import SessionList from "./SessionList";
import UserMenu from "./UserMenu";

interface NavProps {
  icon: IconName;
  label: string;
  active: boolean;
  collapsed: boolean;
}

function NavLink({ href, icon, label, active, collapsed }: NavProps & { href: string }) {
  return (
    <Link href={href} className={`nav-item ${active ? "active" : ""}`} title={collapsed ? label : undefined}>
      <Icon name={icon} />
      {!collapsed && <span>{label}</span>}
    </Link>
  );
}

/** Collapsible navigation: app name, pages, chat sessions and the signed-in user at the bottom. */
export default function Sidebar() {
  const { collapsed, toggleSidebar } = useUiStore();
  const admin = useAuthStore((s) => s.account?.admin);
  const { activeId, newChat } = useChatStore();
  const pathname = usePathname();
  const router = useRouter();

  function startChat() {
    newChat();
    router.push("/");
  }

  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <div className="brand">
        {!collapsed && (
          <span className="brand-name">
            <span className="brand-mark">L</span>
            Lattice
          </span>
        )}
        <button
          className="icon-button"
          onClick={toggleSidebar}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <Icon name="panel" />
        </button>
      </div>

      <nav className="nav">
        <button
          className={`nav-item ${pathname === "/" && !activeId ? "active" : ""}`}
          onClick={startChat}
          title={collapsed ? "New chat" : undefined}
        >
          <Icon name="newChat" />
          {!collapsed && <span>New chat</span>}
        </button>
        <NavLink href="/context" icon="folder" label="Manage Context" active={pathname === "/context"} collapsed={collapsed} />
        {admin && <NavLink href="/users" icon="users" label="Users" active={pathname === "/users"} collapsed={collapsed} />}
        {admin && (
          <a
            className="nav-item"
            href="#"
            target="_blank"
            rel="noreferrer"
            title={collapsed ? "Database" : undefined}
            onClick={(e) => (e.currentTarget.href = `${location.protocol}//${location.hostname}:7474`)}
          >
            <Icon name="database" />
            {!collapsed && <span>Database</span>}
          </a>
        )}
      </nav>

      {collapsed ? <div className="grow" /> : <SessionList />}

      <UserMenu collapsed={collapsed} />
    </aside>
  );
}
