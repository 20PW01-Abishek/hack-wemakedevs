import type { NewUser, UserAccount } from "@/domain/types";
import { post, request } from "./http";

export const userConnector = {
  list: () => request<UserAccount[]>("/users"),
  add: (user: NewUser) => post<{ ok: boolean }>("/users", user),
  setAdmin: (username: string, admin: boolean) =>
    request<{ ok: boolean }>(`/users/${encodeURIComponent(username)}`, { method: "PATCH", body: JSON.stringify({ admin }) }),
  remove: (username: string) =>
    request<{ ok: boolean }>(`/users/${encodeURIComponent(username)}`, { method: "DELETE" }),
};
