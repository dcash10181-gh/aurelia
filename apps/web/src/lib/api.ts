/** Thin typed client for the local AURELIA API (proxied at /api in dev). */

export interface ChatResult { reply: string; provider: string; tool_calls: ToolCall[] }
export interface ToolCall { tool: string; args: Record<string, unknown>; result: string }
export interface Memory { id: string; content: string; tags: string[]; created_at: number }
export interface ToolInfo { name: string; description: string; enabled: boolean }
export interface ProviderInfo { name: string; available: boolean; default: boolean }
export interface Status {
  app: string; version: string; uptime_s: number; python: string;
  providers: Record<string, boolean>; default_provider: string;
  shell_tool_enabled: boolean; data_dir: string;
}

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  status: () => fetch("/api/status").then((r) => j<Status>(r)),
  chat: (message: string, provider?: string | null) =>
    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, provider: provider ?? null }),
    }).then((r) => j<ChatResult>(r)),
  memories: (q?: string) =>
    fetch(`/api/memory${q ? `?q=${encodeURIComponent(q)}` : ""}`).then((r) => j<Memory[]>(r)),
  addMemory: (content: string, tags: string[] = []) =>
    fetch("/api/memory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, tags }),
    }).then((r) => j<Memory>(r)),
  deleteMemory: (id: string) => fetch(`/api/memory/${id}`, { method: "DELETE" }).then((r) => j(r)),
  tools: () => fetch("/api/tools").then((r) => j<ToolInfo[]>(r)),
  providers: () => fetch("/api/providers").then((r) => j<ProviderInfo[]>(r)),
};

/** Parse one SSE frame from /api/chat/stream. Exported for unit tests. */
export function parseSseFrame(frame: string): { token?: string; done?: boolean } {
  const data = frame.replace(/^data:\s*/, "").trim();
  if (data === "[DONE]") return { done: true };
  try {
    const obj = JSON.parse(data);
    return { token: obj.token };
  } catch {
    return {};
  }
}
