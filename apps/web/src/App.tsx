import { useState } from "react";
import { Chat } from "./components/Chat";
import { CommandPalette } from "./components/CommandPalette";
import { Onboarding } from "./components/Onboarding";
import { SidePanel } from "./components/SidePanel";
import { api } from "./lib/api";

export default function App() {
  // Onboarding state intentionally lives in memory + a query param escape hatch:
  // local-first app, no storage writes before consent.
  const [onboarded, setOnboarded] = useState(
    () => new URLSearchParams(location.search).get("skipOnboarding") === "1"
  );
  const [provider, setProvider] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const commands = [
    { label: "Switch model: echo (fallback)", run: () => setProvider("echo") },
    { label: "Switch model: mini LLM (experimental)", run: () => setProvider("mini") },
    { label: "Switch model: ollama (external)", run: () => setProvider("ollama") },
    { label: "Save a memory: hello from the palette", run: () => api.addMemory("hello from the palette").then(() => setRefreshKey(k => k + 1)) },
    { label: "Refresh panels", run: () => setRefreshKey((k) => k + 1) },
  ];

  if (!onboarded) return <Onboarding onDone={() => setOnboarded(true)} />;

  return (
    <div className="h-screen grid grid-cols-1 md:grid-cols-[300px_1fr]">
      <div className="hidden md:block border-r border-line bg-well/40">
        <SidePanel provider={provider} setProvider={setProvider} refreshKey={refreshKey} />
      </div>
      <Chat provider={provider} onToolUse={() => setRefreshKey((k) => k + 1)} />
      <CommandPalette commands={commands} />
    </div>
  );
}
