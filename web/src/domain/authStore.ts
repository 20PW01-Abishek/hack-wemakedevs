import { create } from "zustand";
import { authConnector } from "@/connectors/authConnector";
import { ApiError } from "@/connectors/http";
import { messageOf } from "./messageOf";
import type { Account, Credentials } from "./types";
import { useChatStore } from "./chatStore";

interface AuthState {
  account: Account | null;
  needsSetup: boolean;
  ready: boolean;
  error: string | null;
  init: () => Promise<void>;
  submit: (credentials: Credentials, signup?: boolean) => Promise<void>;
  logout: () => Promise<void>;
}

/** Who is signed in, and whether the first admin still has to be created. */
export const useAuthStore = create<AuthState>((set, get) => ({
  account: null,
  needsSetup: false,
  ready: false,
  error: null,

  init: async () => {
    try {
      set({ account: await authConnector.me(), ready: true });
    } catch (e) {
      const needsSetup = e instanceof ApiError ? await authConnector.needsSetup().catch(() => false) : false;
      set({ needsSetup, ready: true, error: e instanceof ApiError ? null : messageOf(e) });
    }
  },

  submit: async (credentials, signup = false) => {
    set({ error: null });
    try {
      const connect = get().needsSetup ? authConnector.setup : signup ? authConnector.signup : authConnector.login;
      const account = await connect(credentials);
      set({ account, needsSetup: false });
    } catch (e) {
      set({ error: messageOf(e) });
    }
  },

  logout: async () => {
    await authConnector.logout();
    useChatStore.getState().reset();
    set({ account: null });
  },

}));
