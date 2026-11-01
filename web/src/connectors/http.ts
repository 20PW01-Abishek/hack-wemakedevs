export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

/** Call the backend through the Next.js `/api` proxy, sending the session cookie. */
export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, typeof body.detail === "string" ? body.detail : res.statusText);
  }
  return res.json();
}

export function post<T>(path: string, body: unknown = {}): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}
