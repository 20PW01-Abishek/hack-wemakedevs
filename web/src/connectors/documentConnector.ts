import type { ContextDocument, LearnedDocument, StaleDoc } from "@/domain/types";
import { post, request } from "./http";

export const documentConnector = {
  list: () => request<ContextDocument[]>("/documents"),
  staleDocs: () => request<StaleDoc[]>("/alerts"),
  add: (title: string, author: string, text: string) =>
    post<LearnedDocument>("/documents", { title, author: author || null, text }),
  remove: (id: string) => request<{ ok: boolean }>(`/documents/${encodeURIComponent(id)}`, { method: "DELETE" }),
  sync: () => post<{ ingested: number }>("/documents/sync"),
};
