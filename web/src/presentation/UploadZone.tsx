"use client";

import { useRef, useState } from "react";
import { useContextStore } from "@/domain/contextStore";
import Icon from "./Icon";

/** Drop or pick .md, .txt and .csv files for the brain to read. */
export default function UploadZone() {
  const { busy, upload } = useContextStore();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  function pick(files: FileList | null) {
    if (files?.length && !busy) upload(Array.from(files));
  }

  return (
    <div
      className={`dropzone ${over ? "over" : ""}`}
      role="button"
      tabIndex={0}
      onClick={() => input.current?.click()}
      onKeyDown={(e) => e.key === "Enter" && input.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        pick(e.dataTransfer.files);
      }}
    >
      <Icon name="upload" size={24} />
      <strong>{busy ? "Reading..." : "Drop files here or click to upload"}</strong>
      <span className="muted small">.md, .txt or .csv. Large files are split and read in parts.</span>
      <input
        ref={input}
        type="file"
        multiple
        hidden
        accept=".md,.txt,.csv"
        onChange={(e) => {
          pick(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
