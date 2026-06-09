import { useEffect, useState } from "react";

export interface Command { label: string; run: () => void }

export function CommandPalette({ commands }: { commands: Command[] }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault(); setOpen((o) => !o); setQ("");
      }
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!open) return null;
  const filtered = commands.filter((c) => c.label.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="fixed inset-0 bg-black/60 flex items-start justify-center pt-32 z-50"
      role="dialog" aria-modal="true" aria-label="Command palette" onClick={() => setOpen(false)}>
      <div className="w-[480px] max-w-[90vw] bg-panel border border-line rounded-lg shadow-2xl"
        onClick={(e) => e.stopPropagation()}>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Type a command…" aria-label="Search commands"
          className="w-full bg-transparent border-b border-line px-4 py-3 text-sm" />
        <ul className="max-h-72 overflow-y-auto py-1">
          {filtered.map((c) => (
            <li key={c.label}>
              <button className="w-full text-left px-4 py-2 text-sm hover:bg-well"
                onClick={() => { c.run(); setOpen(false); }}>
                {c.label}
              </button>
            </li>
          ))}
          {filtered.length === 0 && <li className="px-4 py-3 text-sm text-faint">No matches.</li>}
        </ul>
        <div className="px-4 py-2 text-[10px] text-faint border-t border-line">
          ⌘K / Ctrl+K to toggle · Esc to close
        </div>
      </div>
    </div>
  );
}
