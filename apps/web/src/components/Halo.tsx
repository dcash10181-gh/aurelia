/** The signature element: a breathing golden halo reflecting agent state.
 *  Original SVG art — concentric strokes only, no copied iconography. */
export function Halo({ state }: { state: "idle" | "thinking" | "tool" | "error" }) {
  const stroke = state === "tool" ? "#5FA8A0" : state === "error" ? "#E06B6B" : "#E8C476";
  return (
    <svg
      width="120" height="120" viewBox="0 0 120 120" role="img"
      aria-label={`Agent is ${state}`}
      className={`halo-breathe ${state === "thinking" ? "halo-thinking" : ""}`}
    >
      <circle cx="60" cy="60" r="52" fill="none" stroke={stroke} strokeOpacity="0.18" strokeWidth="1" />
      <circle cx="60" cy="60" r="40" fill="none" stroke={stroke} strokeOpacity="0.38" strokeWidth="1.5" />
      <circle cx="60" cy="60" r="27" fill="none" stroke={stroke} strokeOpacity="0.7" strokeWidth="2"
        strokeDasharray={state === "thinking" ? "6 10" : "none"} />
      <circle cx="60" cy="60" r="6" fill={stroke} fillOpacity="0.9" />
    </svg>
  );
}
