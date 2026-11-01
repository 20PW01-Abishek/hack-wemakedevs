import type { ChatReply, ChatSession, Message } from "@/domain/types";
import { post, request } from "./http";

export const chatConnector = {
  listSessions: () => request<ChatSession[]>("/sessions"),
  getSession: (id: string, shared: boolean) => request<Message[]>(`/sessions/${id}?shared=${shared}`),
  deleteSession: (id: string, shared: boolean) =>
    request<{ ok: boolean }>(`/sessions/${id}?shared=${shared}`, { method: "DELETE" }),
  send: (question: string, session: string | null, shared: boolean) =>
    post<ChatReply>("/chat", { question, session, shared }),
};
