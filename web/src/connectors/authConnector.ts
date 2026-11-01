import type { Account, Credentials } from "@/domain/types";
import { post, request } from "./http";

export const authConnector = {
  /** Whether the first admin account still has to be created. */
  needsSetup: () => request<{ needs_setup: boolean }>("/status").then((r) => r.needs_setup),
  me: () => request<Account>("/me"),
  setup: (credentials: Credentials) => post<Account>("/setup", credentials),
  signup: (credentials: Credentials) => post<Account>("/signup", credentials),
  login: (credentials: Credentials) => post<Account>("/login", credentials),
  logout: () => post<{ ok: boolean }>("/logout"),
};
