import { ApiError } from "@/connectors/http";

/** A readable message for any error thrown by a connector. */
export function messageOf(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong. Is the backend running?";
}
