import { create } from "zustand";
import { userConnector } from "@/connectors/userConnector";
import { messageOf } from "./messageOf";
import type { NewUser, Notice, UserAccount } from "./types";

interface UserState {
  users: UserAccount[];
  notice: Notice | null;
  load: () => Promise<void>;
  add: (user: NewUser) => Promise<boolean>;
  setAdmin: (username: string, admin: boolean) => Promise<void>;
  remove: (username: string) => Promise<void>;
}

/** Accounts that can sign in, managed by admins. */
export const useUserStore = create<UserState>((set, get) => ({
  users: [],
  notice: null,

  load: async () => {
    try {
      set({ users: await userConnector.list() });
    } catch (e) {
      set({ notice: { text: messageOf(e), error: true } });
    }
  },

  add: async (user) => {
    try {
      await userConnector.add(user);
      set({ notice: { text: `Created ${user.username}`, error: false } });
      await get().load();
      return true;
    } catch (e) {
      set({ notice: { text: messageOf(e), error: true } });
      return false;
    }
  },

  setAdmin: async (username, admin) => {
    try {
      await userConnector.setAdmin(username, admin);
      await get().load();
    } catch (e) {
      set({ notice: { text: messageOf(e), error: true } });
    }
  },

  remove: async (username) => {
    try {
      await userConnector.remove(username);
      set({ notice: { text: `Deleted ${username}`, error: false } });
      await get().load();
    } catch (e) {
      set({ notice: { text: messageOf(e), error: true } });
    }
  },
}));
