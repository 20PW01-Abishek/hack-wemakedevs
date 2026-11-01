import { create } from "zustand";
import { documentConnector } from "@/connectors/documentConnector";
import { messageOf } from "./messageOf";
import type { ContextDocument, Notice, StaleDoc } from "./types";

interface ContextState {
  documents: ContextDocument[];
  alerts: StaleDoc[];
  busy: boolean;
  notice: Notice | null;
  loadDocuments: () => Promise<void>;
  loadAlerts: () => Promise<void>;
  add: (title: string, author: string, text: string) => Promise<boolean>;
  upload: (files: File[]) => Promise<void>;
  sync: () => Promise<void>;
  remove: (doc: ContextDocument) => Promise<void>;
}

/** The documents the brain has learned from, outdated-document alerts and the actions that change them. */
export const useContextStore = create<ContextState>((set, get) => ({
  documents: [],
  alerts: [],
  busy: false,
  notice: null,

  loadDocuments: async () => {
    try {
      set({ documents: await documentConnector.list() });
    } catch (e) {
      set({ notice: { text: messageOf(e), error: true } });
    }
  },

  loadAlerts: async () => {
    try {
      set({ alerts: await documentConnector.staleDocs() });
    } catch {
      set({ alerts: [] });
    }
  },

  add: async (title, author, text) => {
    set({ busy: true, notice: null });
    try {
      const learned = await documentConnector.add(title, author, text);
      set({ busy: false, notice: { text: `Learned: ${learned.summary}`, error: false } });
      await Promise.all([get().loadDocuments(), get().loadAlerts()]);
      return true;
    } catch (e) {
      set({ busy: false, notice: { text: messageOf(e), error: true } });
      return false;
    }
  },

  upload: async (files) => {
    set({ busy: true, notice: null });
    const failed: string[] = [];
    for (const [i, file] of files.entries()) {
      set({ notice: { text: `Reading ${file.name} (${i + 1}/${files.length})...`, error: false } });
      try {
        await documentConnector.add(file.name, "", await file.text());
      } catch {
        failed.push(file.name);
      }
    }
    const done = files.length - failed.length;
    set({
      busy: false,
      notice: failed.length
        ? { text: `${done} added, failed: ${failed.join(", ")}`, error: true }
        : { text: `${done} file${done === 1 ? "" : "s"} added`, error: false },
    });
    await Promise.all([get().loadDocuments(), get().loadAlerts()]);
  },

  sync: async () => {
    set({ busy: true, notice: null });
    try {
      const { ingested } = await documentConnector.sync();
      set({ busy: false, notice: { text: `${ingested} files ingested`, error: false } });
      await Promise.all([get().loadDocuments(), get().loadAlerts()]);
    } catch (e) {
      set({ busy: false, notice: { text: messageOf(e), error: true } });
    }
  },

  remove: async (doc) => {
    try {
      await documentConnector.remove(doc.id);
      set({ notice: { text: `Removed ${doc.name}`, error: false } });
      await Promise.all([get().loadDocuments(), get().loadAlerts()]);
    } catch (e) {
      set({ notice: { text: messageOf(e), error: true } });
    }
  },
}));
