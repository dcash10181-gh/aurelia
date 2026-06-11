/** Thin typed client for the local AURELIA API (proxied at /api in dev). */

export interface ChatResult { reply: string; provider: string; tool_calls: ToolCall[] }
export interface ToolCall { tool: string; args: Record<string, unknown>; result: string }
export interface Memory { id: string; content: string; tags: string[]; created_at: number }
export interface ToolInfo { name: string; description: string; enabled: boolean }
export interface ProviderInfo { name: string; available: boolean; default: boolean }
export interface Status {
  app: string; version: string; uptime_s: number;
  build?: string; python: string;
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

export interface StreamMeta { provider: string; tool_calls: ToolCall[] }

/** Parse one SSE frame from /api/chat/stream. Exported for unit tests. */
export function parseSseFrame(
  frame: string,
): { token?: string; meta?: StreamMeta; toolEvent?: ToolCall; done?: boolean } {
  const data = frame.replace(/^data:\s*/, "").trim();
  if (data === "[DONE]") return { done: true };
  try {
    const obj = JSON.parse(data);
    if (obj.meta) return { meta: obj.meta as StreamMeta };
    if (obj.tool_event) return { toolEvent: obj.tool_event as ToolCall };
    if (typeof obj.token === "string") return { token: obj.token };
    return {};
  } catch {
    return {};
  }
}

/**
 * Stream a chat turn. Calls onToken for each text piece as it arrives and
 * resolves with the meta frame (provider + tool calls) when the stream ends.
 * Frames are buffered on the SSE delimiter (\n\n) because network reads can
 * split or coalesce frames arbitrarily.
 */
export interface Conversation { id: string; title: string; updated_at: number }

export const conversations = {
  list: (): Promise<Conversation[]> =>
    fetch("/api/conversations").then((r) => r.json()),
  create: (): Promise<Conversation> =>
    fetch("/api/conversations", { method: "POST" }).then((r) => r.json()),
  remove: (id: string): Promise<void> =>
    fetch(`/api/conversations/${id}`, { method: "DELETE" }).then(() => undefined),
  messages: (id: string): Promise<{ role: "user" | "assistant"; content: string }[]> =>
    fetch(`/api/messages?conversation_id=${encodeURIComponent(id)}`).then((r) => r.json()),
};

export const workspace = {
  list: (): Promise<string[]> =>
    fetch("/api/workspace").then((r) => r.json()).then((d) => d.files ?? []),
  read: (path: string): Promise<string> =>
    fetch(`/api/workspace/file?path=${encodeURIComponent(path)}`)
      .then((r) => r.json()).then((d) => d.content ?? ""),
};

export async function clearMessages(): Promise<void> {
  await fetch("/api/messages", { method: "DELETE" });
}

export async function chatStream(
  message: string,
  provider: string | null,
  onToken: (t: string) => void,
  onEvent?: (e: ToolCall) => void,
  conversationId?: string,
): Promise<StreamMeta> {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, provider: provider ?? null,
                           conversation_id: conversationId ?? null }),
  });
  if (!res.ok || !res.body) throw new Error(`${res.status}: ${await res.text()}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let meta: StreamMeta = { provider: "unknown", tool_calls: [] };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const parsed = parseSseFrame(frame);
      if (parsed.token !== undefined) onToken(parsed.token);
      if (parsed.toolEvent && onEvent) onEvent(parsed.toolEvent);
      if (parsed.meta) meta = parsed.meta;
      if (parsed.done) return meta;
    }
  }
  return meta;
}
