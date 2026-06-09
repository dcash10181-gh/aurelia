"""AURELIA CLI — control surface for the local agent.

Commands:
  aurelia start            # run API (and print UI instructions)
  aurelia status           # query local API status
  aurelia chat "..."       # one-shot chat through the agent loop
  aurelia tools            # list registered tools
  aurelia memory add/list/search/delete
  aurelia train-mini-llm   # train the from-scratch tiny model
  aurelia generate --prompt "Hello"
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import httpx
import typer

app = typer.Typer(help="AURELIA — your local-first intelligent command layer.",
                  no_args_is_help=True)

API = os.environ.get("AURELIA_API_URL", "http://127.0.0.1:8484")


def _client() -> httpx.Client:
    return httpx.Client(base_url=API, timeout=30)


def _die(msg: str) -> None:
    typer.secho(msg, fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Print CLI version."""
    from . import __version__
    typer.echo(f"aurelia {__version__}")


@app.command()
def start(host: str = "127.0.0.1", port: int = 8484) -> None:
    """Start the backend API with uvicorn (frontend runs via `make dev` or npm)."""
    typer.secho(f"Starting AURELIA API on http://{host}:{port}", fg=typer.colors.YELLOW)
    typer.echo("UI: run `make dev` (or `npm run dev` in apps/web) and open http://localhost:3000")
    # exec uvicorn as a child process; list args, no shell.
    cmd = [sys.executable, "-m", "uvicorn", "aurelia_api.main:app",
           "--host", host, "--port", str(port)]
    raise typer.Exit(code=subprocess.call(cmd))


@app.command()
def status() -> None:
    """Show local agent status."""
    try:
        with _client() as c:
            r = c.get("/api/status")
        typer.echo(json.dumps(r.json(), indent=2))
    except httpx.ConnectError:
        _die(f"AURELIA API not reachable at {API}. Start it with `aurelia start`.")


@app.command()
def chat(message: str, provider: str = typer.Option(None, help="echo | mini | ollama")) -> None:
    """Send one message through the agent loop."""
    try:
        with _client() as c:
            r = c.post("/api/chat", json={"message": message, "provider": provider})
        body = r.json()
        if r.status_code != 200:
            _die(json.dumps(body))
        typer.secho(body["reply"], fg=typer.colors.CYAN)
        if body.get("tool_calls"):
            typer.echo(f"(tools used: {[t['tool'] for t in body['tool_calls']]})")
    except httpx.ConnectError:
        _die(f"AURELIA API not reachable at {API}. Start it with `aurelia start`.")


@app.command()
def tools() -> None:
    """List registered tools."""
    with _client() as c:
        r = c.get("/api/tools")
    for t in r.json():
        flag = "" if t["enabled"] else "  [disabled]"
        typer.echo(f"- {t['name']}{flag}: {t['description']}")


memory_app = typer.Typer(help="Local memory commands.")
app.add_typer(memory_app, name="memory")


@memory_app.command("add")
def memory_add(content: str, tags: str = "") -> None:
    with _client() as c:
        r = c.post("/api/memory", json={"content": content,
                                        "tags": [t for t in tags.split(",") if t]})
    typer.echo(json.dumps(r.json(), indent=2))


@memory_app.command("list")
def memory_list() -> None:
    with _client() as c:
        r = c.get("/api/memory")
    for m in r.json():
        typer.echo(f"{m['id'][:8]}  {m['content'][:70]}")


@memory_app.command("search")
def memory_search(query: str) -> None:
    with _client() as c:
        r = c.get("/api/memory", params={"q": query})
    for m in r.json():
        typer.echo(f"{m['id'][:8]}  {m['content'][:70]}")


@memory_app.command("delete")
def memory_delete(memory_id: str) -> None:
    with _client() as c:
        r = c.delete(f"/api/memory/{memory_id}")
    typer.echo(r.text)


@app.command("train-mini-llm")
def train_mini_llm(steps: int = 300) -> None:
    """Train the from-scratch tiny transformer (CPU, <1 min)."""
    try:
        from aurelia_mini_llm.config import MiniConfig
        from aurelia_mini_llm.train import train
    except ImportError:
        _die("aurelia-mini-llm not installed (requires torch). "
             "Install: pip install -e packages/mini_llm")
    train(MiniConfig(max_steps=steps))
    typer.secho("Done. Try: aurelia generate --prompt 'aurelia '", fg=typer.colors.GREEN)


@app.command()
def generate(prompt: str = typer.Option("aurelia ", "--prompt"),
             tokens: int = 160) -> None:
    """Generate text with the trained mini LLM (educational output only)."""
    try:
        from aurelia_mini_llm.generate import load_generator
    except ImportError:
        _die("aurelia-mini-llm not installed (requires torch).")
    try:
        gen = load_generator(max_new_tokens=tokens)
    except FileNotFoundError as e:
        _die(str(e))
    typer.echo(gen(prompt))


if __name__ == "__main__":
    app()
