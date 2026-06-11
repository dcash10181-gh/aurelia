import { useEffect, useRef, useState } from "react";
import { api, workspace, Memory, ProviderInfo, Status, ToolInfo } from "../lib/api";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-b border-line pb-4 mb-4">
      <h2 className="text-[11px] uppercase tracking-[0.25em] text-faint mb-2">{title}</h2>
      {children}
    </section>
  );
}

export function SidePanel({
  provider, setProvider, refreshKey,
}: { provider: string | null; setProvider: (p: string) => void; refreshKey: number }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [memInput, setMemInput] = useState("");
  const [err, setErr] = useState(false);
  // The polling interval's closure captures `provider` from the render it
  // was created in (perpetually null), so reading the prop directly here
  // would reset the user's selection to the default on every poll. The ref
  // always reflects the latest value; only an unset selection is defaulted.
  const providerRef = useRef(provider);
  providerRef.current = provider;
  const [wsFiles, setWsFiles] = useState<string[]>([]);
  const [wsOpen, setWsOpen] = useState<string | null>(null);
  const [wsContent, setWsContent] = useState("");

  async function openWsFile(path: string) {
    if (wsOpen === path) { setWsOpen(null); return; }
    setWsOpen(path);
    setWsContent(await workspace.read(path).catch(() => "(unreadable)"));
  }

  async function refresh() {
    try {
      const [s, t, p, m, w] = await Promise.all([
        api.status(), api.tools(), api.providers(), api.memories(),
        workspace.list().catch(() => [] as string[]),
      ]);
      setStatus(s); setTools(t); setProviders(p); setMemories(m); setWsFiles(w); setErr(false);
      if (!providerRef.current) setProvider(s.default_provider);
    } catch { setErr(true); }
  }
  useEffect(() => { refresh(); const t = setInterval(refresh, 8000); return () => clearInterval(t); },
    [refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  async function addMemory() {
    if (!memInput.trim()) return;
    await api.addMemory(memInput.trim());
    setMemInput(""); refresh();
  }

  if (err) return (
    <aside className="p-5 text-sm text-faint">
      <p className="text-gold mb-2">Backend offline</p>
      <p>Start it in a terminal:</p>
      <code className="font-mono text-mist block mt-2 bg-well p-2 rounded">aurelia start</code>
    </aside>
  );

  return (
    <aside className="p-5 overflow-y-auto h-full" aria-label="System panels">
      <Section title="System">
        <ul className="text-xs space-y-1 font-mono text-mist">
          <li><span className="text-teal">●</span> local · v{status?.version ?? "…"}</li>
          <li>uptime {status ? Math.round(status.uptime_s) : "…"}s · py {status?.python}</li>
          <li className="text-mist/50">build {status?.build ?? "…"}</li>
          <li>shell tool: {status?.shell_tool_enabled ? "enabled ⚠" : "disabled (safe)"}</li>
        </ul>
      </Section>

      <Section title="Model">
        <div role="radiogroup" aria-label="Model provider" className="space-y-1">
          {providers.map((p) => (
            <button key={p.name} role="radio" aria-checked={provider === p.name}
              onClick={() => setProvider(p.name)} disabled={!p.available}
              className={"w-full text-left text-sm px-3 py-1.5 rounded border " +
                (provider === p.name ? "border-gold/70 text-gold" : "border-line text-mist") +
                (p.available ? "" : " opacity-40")}>
              {p.name}{!p.available && " (unavailable)"}{p.default && " · default"}
            </button>
          ))}
        </div>
      </Section>

      <Section title="Tools">
        <ul className="text-xs space-y-1.5">
          {tools.map((t) => (
            <li key={t.name} className={t.enabled ? "" : "opacity-50"}>
              <span className="font-mono text-teal">{t.name}</span>
              {!t.enabled && <span className="text-faint"> — disabled</span>}
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Workspace">
        {wsFiles.length === 0 ? (
          <p className="text-xs text-mist/50">No files yet — ask the agent to write one.</p>
        ) : (
          <ul className="text-xs space-y-1">
            {wsFiles.map((f) => (
              <li key={f}>
                <button onClick={() => openWsFile(f)}
                        className="text-teal hover:text-gold text-left break-all">
                  {wsOpen === f ? "▾ " : "▸ "}{f}
                </button>
                {wsOpen === f && (
                  <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded border border-line bg-well p-2 text-[10px] text-mist/90">
                    {wsContent}
                  </pre>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Memory">
        <div className="flex gap-1 mb-2">
          <label htmlFor="mem-input" className="sr-only">New memory</label>
          <input id="mem-input" value={memInput} onChange={(e) => setMemInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addMemory()}
            placeholder="Remember something…"
            className="flex-1 bg-well border border-line rounded px-2 py-1 text-xs" />
          <button onClick={addMemory}
            className="text-xs px-2 rounded bg-panel border border-line hover:border-gold/50">
            Save
          </button>
        </div>
        <ul className="text-xs space-y-1.5">
          {memories.slice(0, 8).map((m) => (
            <li key={m.id} className="flex justify-between gap-2 group">
              <span className="truncate">{m.content}</span>
              <button aria-label={`Delete memory: ${m.content.slice(0, 30)}`}
                onClick={() => api.deleteMemory(m.id).then(refresh)}
                className="text-faint hover:text-gold">×</button>
            </li>
          ))}
          {memories.length === 0 && <li className="text-faint">Nothing saved yet.</li>}
        </ul>
      </Section>
    </aside>
  );
}
