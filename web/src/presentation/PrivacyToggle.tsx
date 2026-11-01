"use client";

import { useChatStore } from "@/domain/chatStore";
import Icon from "./Icon";

/** Switch a chat between private (only you) and shared (everyone). Fixed once the chat has started. */
export default function PrivacyToggle() {
  const { shared, setShared, messages } = useChatStore();
  const locked = messages.length > 0;

  return (
    <button
      type="button"
      role="switch"
      aria-checked={!shared}
      className="switch"
      disabled={locked}
      onClick={() => setShared(!shared)}
      title={locked ? "Privacy is fixed once the chat has started" : "Private chats are visible only to you. Turn off to share with everyone."}
    >
      <Icon name={shared ? "globe" : "lock"} size={15} />
      <span>{shared ? "Shared" : "Private"}</span>
      <span className="track">
        <span className="thumb" />
      </span>
    </button>
  );
}
