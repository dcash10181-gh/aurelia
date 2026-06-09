# Contributing to AURELIA

1. Fork and clone, then run `./install.sh --local` (uses the current checkout).
2. Create a branch: `git checkout -b feat/my-change`.
3. Run the full test suite before opening a PR: `./scripts/test_all.sh`.
4. Lint: `ruff check services packages` and `npm run lint` in `apps/web`.
5. Add tests for new behavior. Tools/plugins need a registry test
   (see docs/plugin_api.md).
6. Keep the security posture: no telemetry, no default-on shell execution,
   filesystem access sandboxed to the data directory.

Commit style: imperative, scoped (`api: add export endpoint`).
