// Tailwind v3 (CLI standalone). Cores vêm de variáveis CSS definidas em tailwind/input.css (claro/escuro).
module.exports = {
  content: ["./pricetrail/web/**/*.html", "./pricetrail/web/**/*.js"],
  theme: {
    extend: {
      colors: {
        surface: "var(--surface)",
        raised: "var(--raised)",
        ink: "var(--text)",
        muted: "var(--muted)",
        line: "var(--line)",
        accent: "var(--accent)",
        "accent-ink": "var(--accent-text)",
        warn: "var(--warn)",
        "warn-bg": "var(--warn-bg)",
        up: "var(--up)",
        down: "var(--down)",
        ok: "var(--ok)",
      },
      minHeight: { touch: "44px" },
      minWidth: { touch: "44px" },
    },
  },
};
