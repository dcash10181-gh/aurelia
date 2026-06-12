"""Hyperparameters for the mini LLM. Small on purpose: trains on CPU in <1 min."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "tiny_corpus.txt"
DEFAULT_CKPT = Path.home() / ".aurelia" / "mini_llm.pt"

# AURELIA-1: the larger, BPE-based educational model. Still small enough to
# train on a CPU in a couple of minutes, but ~5M params on a real corpus
# produces word-like English instead of character babble. NOT intelligent —
# the UI and outputs say so — but a clear step up from the mini model.
AURELIA1_DATA = Path(__file__).resolve().parent.parent / "data" / "corpus_aurelia1.txt"
AURELIA1_CKPT = Path.home() / ".aurelia" / "aurelia1.pt"


@dataclass
class Aurelia1Config:
    block_size: int = 128
    n_layer: int = 6
    n_head: int = 6
    n_embd: int = 288
    dropout: float = 0.1
    vocab_size: int = 0       # set from BPE tokenizer at train time
    bpe_vocab_size: int = 2048
    lr: float = 6e-4
    batch_size: int = 32
    max_steps: int = 3000
    seed: int = 1337


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
