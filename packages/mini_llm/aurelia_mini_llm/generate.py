"""Inference for the mini LLM.

Usage:
    python -m aurelia_mini_llm.generate --prompt "Hello"
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

import torch

from .config import DEFAULT_CKPT, MiniConfig
from .model import MiniGPT
from .tokenizer import CharTokenizer


def load_generator(checkpoint: str | Path | None = None,
                   max_new_tokens: int = 160) -> Callable[[str], str]:
    """Load a checkpoint and return prompt -> text. Raises if missing."""
    ckpt_path = Path(checkpoint or DEFAULT_CKPT)
    if not ckpt_path.exists():
        raise FileNotFoundError(
            f"No checkpoint at {ckpt_path}. Train first: `aurelia train-mini-llm`")
    blob = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    cfg = MiniConfig(**blob["config"])
    tok = CharTokenizer(blob["stoi"])
    model = MiniGPT(cfg)
    model.load_state_dict(blob["model"])
    model.eval()

    def generate(prompt: str) -> str:
        ids = tok.encode(prompt) or [0]
        idx = torch.tensor([ids[-cfg.block_size:]], dtype=torch.long)
        out = model.generate(idx, max_new_tokens=max_new_tokens)
        return tok.decode(out[0].tolist())

    return generate


def load_stream_generator(checkpoint: str | Path | None = None,
                          max_new_tokens: int = 160):
    """Load a checkpoint and return prompt -> iterator of decoded text pieces.

    Char-level tokenizer ⇒ one token == one character, so each yielded piece
    is a single character. The API layer forwards them as SSE frames.
    """
    ckpt_path = Path(checkpoint or DEFAULT_CKPT)
    if not ckpt_path.exists():
        raise FileNotFoundError(
            f"No checkpoint at {ckpt_path}. Train first: `aurelia train-mini-llm`")
    blob = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    cfg = MiniConfig(**blob["config"])
    tok = CharTokenizer(blob["stoi"])
    model = MiniGPT(cfg)
    model.load_state_dict(blob["model"])
    model.eval()

    def stream(prompt: str):
        ids = tok.encode(prompt) or [0]
        idx = torch.tensor([ids[-cfg.block_size:]], dtype=torch.long)
        for token_id in model.stream_generate(idx, max_new_tokens=max_new_tokens):
            yield tok.decode([token_id])

    return stream


def main() -> None:
    p = argparse.ArgumentParser(description="Generate text with the mini LLM")
    p.add_argument("--prompt", type=str, default="Aurelia ")
    p.add_argument("--checkpoint", type=str, default=None)
    p.add_argument("--tokens", type=int, default=160)
    a = p.parse_args()
    gen = load_generator(a.checkpoint, max_new_tokens=a.tokens)
    print(gen(a.prompt))


if __name__ == "__main__":
    main()
