/** Oxidized-bronze observatory palette. Dark-first, AA contrast on body text. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        night: "#10171A",      // base
        well: "#0B1113",       // recessed surfaces
        panel: "#161F23",      // raised surfaces
        line: "#243036",       // hairlines
        mist: "#C9D4D2",       // body text (AA on night)
        faint: "#7E8E8C",      // secondary text
        gold: "#E8C476",       // primary accent
        bronze: "#9A7B3F",     // deep accent
        teal: "#5FA8A0"        // tool/system accent
      },
      fontFamily: {
        display: ["Palatino", "'Iowan Old Style'", "'Palatino Linotype'", "Georgia", "serif"],
        body: ["system-ui", "-apple-system", "'Segoe UI'", "sans-serif"],
        mono: ["ui-monospace", "'SF Mono'", "Menlo", "monospace"]
      }
    }
  },
  plugins: []
};
