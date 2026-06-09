import { FormEvent, useEffect, useRef, useState } from "react";
import { api, ChatResult } from "../lib/api";
import { Halo } from "./Halo";

interface Msg { role: "user" | "assistant"; content: string; meta?: string }

export function Chat({ provider, onToolUse }: { provider: string | null; onToolUse: () => void }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [state, setState] = useState<"idle" | "thinking" | "tool">("idle");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [msgs]);

  async function send(e?: FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || state !== "idle") return;
    setInput("");
    setMsgs((m) => [...m, { role: "user", content: text }]);
    setState("thinking");
    try {
      const res: ChatResult = await api.chat(text, provider);
      if (res.tool_calls.length) { setState("tool"); onToolUse(); }
      setMsgs((m) => [...m, { role: "assistant", content: res.reply, meta: res.provider }]);
    } catch (err) {
      setMsgs((m) => [...m, {
        role: "assistant",
        content: `Backend unreachable. Start it with \`aurelia start\`, then retry. (${err})`,
        meta: "system",
      }]);
    } finally {
      setTimeout(() => setState("idle"), 400);
    }
  }

  return (
    <section className="flex h-full flex-col" aria-label="Conversation">
      <div className="flex flex-col items-center pt-6 pb-2">
        <Halo state={state} />
        <h1 className="font-display text-3xl tracking-[0.35em] text-gold mt-2">AURELIA</h1>
        <p className="text-faint text-xs tracking-widest uppercase mt-1">
          your local-first intelligent command layer
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4" role="log" aria-live="polite">
        {msgs.length === 0 && (
          <p className="text-faint text-sm text-center mt-8">
            Everything runs on this machine. Try “calculate 12*12”, “what time is it”,
            or “save note ideas: ship the thing”.
          </p>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <div className={
              "inline-block max-w-[80%] rounded-lg px-4 py-2 text-sm whitespace-pre-wrap " +
              (m.role === "user" ? "bg-panel border border-line" : "bg-well border border-bronze/30")
            }>
              {m.content}
            </div>
            {m.meta && <div className="text-[10px] text-faint mt-1 font-mono">{m.meta}</div>}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <form onSubmit={send} className="border-t border-line p-4 flex gap-2">
        <label htmlFor="chat-input" className="sr-only">Message AURELIA</label>
        <input
          id="chat-input" value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="Ask, command, or compute…" autoComplete="off"
          className="flex-1 bg-well border border-line rounded-md px-4 py-2 text-sm
                     placeholder:text-faint focus:border-gold/60"
        />
        <button type="submit" disabled={state !== "idle"}
          className="px-5 py-2 rounded-md bg-gold/90 text-night font-medium text-sm
                     hover:bg-gold disabled:opacity-40">
          Send
        </button>
      </form>
    </section>
  );
}
