import { create } from "zustand";
import { chatConnector } from "@/connectors/chatConnector";
import { messageOf } from "./messageOf";
import type { ChatSession, Message } from "./types";

interface ChatState {
  sessions: ChatSession[];
  activeId: string | null;
  messages: Message[];
  shared: boolean;
  sending: boolean;
  error: string | null;
  loadSessions: () => Promise<void>;
  newChat: () => void;
  openSession: (session: ChatSession) => Promise<void>;
  removeSession: (session: ChatSession) => Promise<void>;
  setShared: (shared: boolean) => void;
  send: (question: string) => Promise<void>;
  reset: () => void;
}

const empty = { sessions: [], activeId: null, messages: [], shared: false, sending: false, error: null };

/** Chat sessions, the open conversation and the private/shared choice for a new chat. */
export const useChatStore = create<ChatState>((set, get) => ({
  ...empty,

  loadSessions: async () => {
    try {
      set({ sessions: await chatConnector.listSessions() });
    } catch (e) {
      set({ error: messageOf(e) });
    }
  },

  newChat: () => set({ activeId: null, messages: [], error: null }),

  openSession: async (session) => {
    set({ activeId: session.id, shared: session.shared, messages: [], error: null });
    try {
      const messages = await chatConnector.getSession(session.id, session.shared);
      if (get().activeId === session.id) set({ messages });
    } catch (e) {
      set({ error: messageOf(e) });
    }
  },

  removeSession: async (session) => {
    try {
      await chatConnector.deleteSession(session.id, session.shared);
      if (get().activeId === session.id) get().newChat();
      await get().loadSessions();
    } catch (e) {
      set({ error: messageOf(e) });
    }
  },

  setShared: (shared) => set({ shared }),

  send: async (question) => {
    const { activeId, shared, messages } = get();
    set({ messages: [...messages, { role: "user", text: question }], sending: true, error: null });
    try {
      const reply = await chatConnector.send(question, activeId, shared);
      set((s) => ({
        activeId: reply.session,
        messages: [...s.messages, { role: "assistant", text: reply.answer, steps: reply.steps, graph: reply.graph }],
        sending: false,
      }));
      await get().loadSessions();
    } catch (e) {
      set({ sending: false, error: messageOf(e) });
    }
  },

  reset: () => set(empty),
}));
