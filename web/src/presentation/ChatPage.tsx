"use client";

import { useEffect, useRef } from "react";
import { useChatStore } from "@/domain/chatStore";
import AlertsBanner from "./AlertsBanner";
import ChatHeader from "./ChatHeader";
import Composer from "./Composer";
import MessageBubble from "./MessageBubble";

/** The conversation page: header with privacy switch, alerts, messages and the input box. */
export default function ChatPage() {
  const { messages, sending, error } = useChatStore();
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  return (
    <div className="chat">
      <ChatHeader />
      <AlertsBanner />
      <div className="messages">
        {messages.length === 0 && (
          <div className="empty">
            <h2>What do you want to know?</h2>
            <p className="muted">Ask why something changed, who decided, where it is documented, and who is affected.</p>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}
        {sending && <p className="muted">Walking the graph...</p>}
        {error && <p className="error">{error}</p>}
        <div ref={end} />
      </div>
      <Composer />
    </div>
  );
}
