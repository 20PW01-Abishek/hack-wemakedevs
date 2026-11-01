"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/domain/authStore";
import { useChatStore } from "@/domain/chatStore";
import { useContextStore } from "@/domain/contextStore";
import { useUiStore } from "@/domain/uiStore";
import LoginScreen from "./LoginScreen";
import Sidebar from "./Sidebar";

/** Gate for the whole app: the login screen until someone is signed in, then the sidebar and the current page. */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const { account, ready, init } = useAuthStore();
  const loadSessions = useChatStore((s) => s.loadSessions);
  const loadAlerts = useContextStore((s) => s.loadAlerts);

  useEffect(() => {
    useUiStore.persist.rehydrate();
    init();
  }, [init]);

  useEffect(() => {
    if (account) {
      loadSessions();
      loadAlerts();
    }
  }, [account, loadSessions, loadAlerts]);

  if (!ready) return <div className="center muted">Loading...</div>;
  if (!account) return <LoginScreen />;

  return (
    <div className="shell">
      <Sidebar />
      <div className="content">{children}</div>
    </div>
  );
}
