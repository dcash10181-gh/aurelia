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

## Web fetch (SSRF containment)
`web.fetch` performs user-directed, read-only HTTP(S) GETs. Every resolved
address must be globally routable: loopback, private, link-local, and
reserved ranges are refused, and resolution failures fail closed. This
prevents the model from probing the AURELIA API, Ollama, or anything on the
local network. No POST, no cookies, no auth — side-effectful web actions are
deliberately not a feature at this trust level. Disable entirely with
`AURELIA_ENABLE_WEB_TOOL=false`.

## Workspace sandbox
`files.*` tools operate only inside `<data_dir>/workspace`. Every path is
resolved and must remain inside the root; traversal attempts raise. Read and
write sizes are capped.

## Reporting a vulnerability
Open a private security advisory on the GitHub repository, or open an issue
with the label `security` if the problem is not sensitive. Please include
reproduction steps. Expect an initial response within 7 days.
