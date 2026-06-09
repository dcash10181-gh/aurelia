"""Hyperparameters for the mini LLM. Small on purpose: trains on CPU in <1 min."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "tiny_corpus.txt"
DEFAULT_CKPT = Path.home() / ".aurelia" / "mini_llm.pt"


@dataclass
class MiniConfig:
    block_size: int = 64     # context length (characters)
    n_layer: int = 2
    n_head: int = 2
    n_embd: int = 64
    dropout: float = 0.1
    vocab_size: int = 0      # set from tokenizer at train time
    lr: float = 3e-3
    batch_size: int = 16
    max_steps: int = 300
    seed: int = 1337
