"use client";

import ReactMarkdown from "react-markdown";
import type { Message } from "@/domain/types";
import PathGraph from "./PathGraph";

/** One chat message. Assistant messages also show the answer path graph and the tool calls. */
export default function MessageBubble({ message }: { message: Message }) {
  return (
    <div className={`bubble ${message.role}`}>
      <ReactMarkdown>{message.text}</ReactMarkdown>
      {message.graph && <PathGraph graph={message.graph} />}
      {message.steps && message.steps.length > 0 && (
        <details className="steps">
          <summary>Graph tool calls ({message.steps.length})</summary>
          {message.steps.map((s, i) => (
            <code key={i}>
              {s.name}({JSON.stringify(s.args)})
            </code>
          ))}
        </details>
      )}
    </div>
  );
}
