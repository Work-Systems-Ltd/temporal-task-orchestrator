/**
 * Shared HTTP client — centralises fetch with error handling.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    window.location.href = "/login";
    throw new ApiError(401, "Session expired");
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function get<T>(url: string): Promise<T> {
  const res = await fetch(url);
  return handleResponse<T>(res);
}

export async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<T>(res);
}

export async function postForm(
  url: string,
  data: Record<string, string>,
): Promise<Response> {
  const res = await fetch(url, {
    method: "POST",
    body: new URLSearchParams(data),
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  if (res.status === 401) {
    window.location.href = "/login";
  }
  return res;
}

export async function fetchHtml(url: string): Promise<string> {
  const res = await fetch(url, { headers: { Accept: "text/html" } });
  if (res.status === 401) {
    window.location.href = "/login";
    throw new ApiError(401, "Session expired");
  }
  return res.text();
}
