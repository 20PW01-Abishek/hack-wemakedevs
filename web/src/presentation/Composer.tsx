"use client";

import { useState } from "react";
import { useChatStore } from "@/domain/chatStore";

/** The question box. Enter sends, Shift+Enter adds a new line. */
export default function Composer() {
  const { send, sending } = useChatStore();
  const [text, setText] = useState("");

  function submit() {
    const question = text.trim();
    if (!question || sending) return;
    setText("");
    send(question);
  }

  return (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <textarea
        rows={2}
        value={text}
        placeholder="Ask about a person, concept, decision or document"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
      />
      <button className="primary" disabled={sending || !text.trim()}>
        Send
      </button>
    </form>
  );
}
