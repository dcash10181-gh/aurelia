"""Tiny dataset utilities: load corpus text, build (x, y) next-char batches."""
from __future__ import annotations

from pathlib import Path

import torch

from .config import DEFAULT_DATA


def load_corpus(path: str | Path | None = None) -> str:
    return Path(path or DEFAULT_DATA).read_text(encoding="utf-8")


def get_batch(data: torch.Tensor, block_size: int, batch_size: int,
              generator: torch.Generator | None = None):
    ix = torch.randint(len(data) - block_size - 1, (batch_size,), generator=generator)
    x = torch.stack([data[i:i + block_size] for i in ix])
    y = torch.stack([data[i + 1:i + 1 + block_size] for i in ix])
    return x, y
