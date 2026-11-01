"use client";

import { useChatStore } from "@/domain/chatStore";
import PrivacyToggle from "./PrivacyToggle";

/** Title of the open conversation with its privacy switch. */
export default function ChatHeader() {
  const title = useChatStore((s) => s.sessions.find((x) => x.id === s.activeId)?.title ?? "New chat");

  return (
    <header className="page-header">
      <h1 title={title}>{title}</h1>
      <PrivacyToggle />
    </header>
  );
}
