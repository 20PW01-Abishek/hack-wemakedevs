"use client";

import { useState } from "react";
import { useContextStore } from "@/domain/contextStore";

/** Paste text instead of uploading a file. */
export default function PasteForm() {
  const { busy, add } = useContextStore();
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [text, setText] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (await add(title, author, text)) {
      setTitle("");
      setAuthor("");
      setText("");
    }
  }

  return (
    <details className="card">
      <summary>Or paste text</summary>
      <form className="stack" onSubmit={submit}>
        <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <input placeholder="Author (defaults to you)" value={author} onChange={(e) => setAuthor(e.target.value)} />
        <textarea rows={6} placeholder="Paste the document text" value={text} onChange={(e) => setText(e.target.value)} />
        <button className="primary" disabled={busy || !title || !text}>
          {busy ? "Reading..." : "Add to graph"}
        </button>
      </form>
    </details>
  );
}
