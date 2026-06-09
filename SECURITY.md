# Security Policy

## Design posture
AURELIA is local-first. The threat model assumes the API is only reachable
from the machine it runs on.

- The API binds to `127.0.0.1` by default. Do not expose it to a network
  without adding authentication — there is none built in.
- **No telemetry.** The app makes zero outbound requests except the optional,
  user-configured Ollama adapter to `localhost`.
- **Shell tool is disabled by default.** Enable only via
  `AURELIA_ENABLE_SHELL_TOOL=true`, knowing it runs commands as your user.
  Even when enabled, commands run with `shell=False` semantics (argument
  lists, no metacharacter expansion) and a 15s timeout.
- **Filesystem tools are sandboxed.** Notes resolve paths and reject anything
  escaping `<data_dir>/notes`.
- **No eval/exec.** The calculator parses with `ast` against an operator
  allowlist.
- **No secrets in the repo.** `.env.example` only; `.env` is git-ignored.
- The mini LLM checkpoint loader uses `torch.load` on a file the user
  trained locally. Do not load checkpoints from untrusted sources.

## Reporting a vulnerability
Open a private security advisory on the GitHub repository, or open an issue
with the label `security` if the problem is not sensitive. Please include
reproduction steps. Expect an initial response within 7 days.
