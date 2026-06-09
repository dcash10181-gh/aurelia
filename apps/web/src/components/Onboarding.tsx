export function Onboarding({ onDone }: { onDone: () => void }) {
  return (
    <div className="fixed inset-0 bg-night flex items-center justify-center z-50 p-6">
      <div className="max-w-md text-center">
        <h1 className="font-display text-4xl tracking-[0.3em] text-gold mb-3">AURELIA</h1>
        <p className="text-faint text-sm tracking-widest uppercase mb-8">
          your local-first intelligent command layer
        </p>
        <ul className="text-left text-sm space-y-3 mb-8 text-mist">
          <li><span className="text-gold">●</span> Runs entirely on this machine — no cloud, no telemetry.</li>
          <li><span className="text-gold">●</span> Tools, memory, and models live in your local data folder.</li>
          <li><span className="text-gold">●</span> Press <kbd className="font-mono bg-well px-1 rounded">⌘K</kbd> anywhere for the command palette.</li>
          <li><span className="text-teal">●</span> The shell tool is off until you turn it on. Stay in control.</li>
        </ul>
        <button onClick={onDone} autoFocus
          className="px-8 py-2.5 rounded-md bg-gold text-night font-medium hover:bg-gold/90">
          Enter
        </button>
      </div>
    </div>
  );
}
