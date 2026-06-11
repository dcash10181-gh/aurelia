import { FormEvent, useEffect, useRef, useState } from "react";
import { chatStream, Conversation, conversations, ToolCall } from "../lib/api";
import { Halo } from "./Halo";

interface Msg { role: "user" | "assistant"; content: string; meta?: string; steps?: ToolCall[] }

export function Chat({ provider, onToolUse }: { provider: string | null; onToolUse: () => void }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [state, setState] = useState<"idle" | "thinking" | "tool">("idle");
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [convId, setConvId] = useState<string>("default");

  // Load the conversation list once; resume the most recent conversation
  // (people close laptops mid-thought — resuming is the daily-driver default).
  useEffect(() => {
    conversations.list().then((cs) => {
      setConvs(cs);
      const latest = cs[0]?.id ?? "default";
      setConvId(latest);
      conversations.messages(latest).then((ms) =>
        setMsgs(ms.map((m) => ({ role: m.role, content: m.content }))));
    }).catch(() => {/* backend down; Chat still renders */});
  }, []);

  async function switchConversation(id: string) {
    setConvId(id);
    const ms = await conversations.messages(id);
    setMsgs(ms.map((m) => ({ role: m.role, content: m.content })));
  }
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
      // Append an empty assistant bubble, then fill it token-by-token. The
      // updater always rewrites the LAST message, so concurrent renders stay
      // consistent without tracking an index.
      setMsgs((m) => [...m, { role: "assistant", content: "", meta: undefined }]);
      const meta = await chatStream(
        text, provider,
        (t) =>
          setMsgs((m) => {
            const next = m.slice();
            const last = next[next.length - 1];
            next[next.length - 1] = { ...last, content: last.content + t };
            return next;
          }),
        (ev) => {
          setState("tool");
          setMsgs((m) => {
            const next = m.slice();
            const last = next[next.length - 1];
            next[next.length - 1] = { ...last, steps: [...(last.steps ?? []), ev] };
            return next;
          });
        },
        convId,
      );
      // First message titles the conversation server-side; refresh the list.
      conversations.list().then(setConvs).catch(() => {});
      if (meta.tool_calls.length) { setState("tool"); onToolUse(); }
      setMsgs((m) => {
        const next = m.slice();
        next[next.length - 1] = { ...next[next.length - 1], meta: meta.provider };
        return next;
      });
    } catch (err) {
      // Replace the (possibly empty) streaming bubble with the error.
      setMsgs((m) => {
        const next = m.slice();
        const last = next[next.length - 1];
        const errMsg = {
          role: "assistant" as const,
          content: `Backend unreachable. Start it with \`aurelia start\`, then retry. (${err})`,
          meta: "system",
        };
        if (last?.role === "assistant" && last.content === "") next[next.length - 1] = errMsg;
        else next.push(errMsg);
        return next;
      });
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
            {m.steps && m.steps.length > 0 && (
              <ul className="text-[10px] font-mono text-teal/80 mb-1 space-y-0.5">
                {m.steps.map((s2, j) => (
                  <li key={j}>⚙ {s2.tool} → {String(s2.result).slice(0, 60)}</li>
                ))}
              </ul>
            )}
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
