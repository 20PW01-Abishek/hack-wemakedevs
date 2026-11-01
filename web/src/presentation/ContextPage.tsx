"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/domain/authStore";
import { useContextStore } from "@/domain/contextStore";
import AlertsBanner from "./AlertsBanner";
import DocumentTable from "./DocumentTable";
import PasteForm from "./PasteForm";
import UploadZone from "./UploadZone";

/** Manage what the brain knows: upload or paste documents, sync the documentation folder, remove documents. */
export default function ContextPage() {
  const admin = useAuthStore((s) => s.account?.admin);
  const { busy, notice, loadDocuments, sync } = useContextStore();

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  return (
    <div className="page">
      <header className="page-header">
        <h1>Manage Context</h1>
        {admin && (
          <button onClick={sync} disabled={busy}>
            Sync documentation folder
          </button>
        )}
      </header>
      <div className="page-body">
        <UploadZone />
        <PasteForm />
        {notice && <p className={notice.error ? "error" : "success"}>{notice.text}</p>}
        <AlertsBanner />
        <h2>Documents</h2>
        <DocumentTable />
      </div>
    </div>
  );
}
