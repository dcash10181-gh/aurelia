"""Byte-level BPE tokenizer for the AURELIA-1 model.

Why BPE now (vs. the char tokenizer the original mini LLM uses): with a real
multi-hundred-KB corpus, subword units let a small model spend its capacity on
word structure instead of re-learning spelling every time. Byte-level base
(0-255) means there are no out-of-vocabulary characters ever — any UTF-8 text
encodes — while learned merges capture common letter sequences and whole words.

Dependency-free and inspectable: the merge-learning loop is the textbook BPE
algorithm, ~40 lines, no tokenizers/sentencepiece. Trains in seconds on the
bundled corpus. This is an educational model; the tokenizer matches that bar.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


class BPETokenizer:
    def __init__(self, merges: list[tuple[int, int]] | None = None,
                 vocab: dict[int, bytes] | None = None):
        # merges: ordered list of byte-pair merges learned during training.
        # vocab: token id -> raw bytes, for decoding.
        self.merges = merges or []
        self.vocab = vocab or {i: bytes([i]) for i in range(256)}
        self._merge_rank = {pair: i for i, pair in enumerate(self.merges)}

    @property
    def vocab_size(self) -> int:
        return len(self.vocab)

    @classmethod
    def train(cls, text: str, vocab_size: int = 1024) -> "BPETokenizer":
        """Learn merges until the vocabulary reaches vocab_size (>=256)."""
        assert vocab_size >= 256, "byte-level base needs at least 256 tokens"
        ids = list(text.encode("utf-8"))
        merges: list[tuple[int, int]] = []
        vocab = {i: bytes([i]) for i in range(256)}
        next_id = 256
        target_merges = vocab_size - 256
        for _ in range(target_merges):
            pairs = Counter(zip(ids, ids[1:]))
            if not pairs:
                break
            top = pairs.most_common(1)[0][0]
            ids = _merge(ids, top, next_id)
            merges.append(top)
            vocab[next_id] = vocab[top[0]] + vocab[top[1]]
            next_id += 1
        return cls(merges, vocab)

    def encode(self, text: str) -> list[int]:
        ids = list(text.encode("utf-8"))
        # Apply merges in the order they were learned (greedy by rank).
        while len(ids) >= 2:
            pairs = set(zip(ids, ids[1:]))
            cand = min(pairs, key=lambda p: self._merge_rank.get(p, float("inf")))
            if cand not in self._merge_rank:
                break
            ids = _merge(ids, cand, 256 + self._merge_rank[cand])
        return ids

    def decode(self, ids: list[int]) -> str:
        data = b"".join(self.vocab.get(i, b"") for i in ids)
        return data.decode("utf-8", errors="replace")

    def save(self, path: str | Path) -> None:
        blob = {
            "merges": [list(p) for p in self.merges],
            "vocab": {str(k): list(v) for k, v in self.vocab.items()},
        }
        Path(path).write_text(json.dumps(blob), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "BPETokenizer":
        blob = json.loads(Path(path).read_text(encoding="utf-8"))
        merges = [tuple(p) for p in blob["merges"]]
        vocab = {int(k): bytes(v) for k, v in blob["vocab"].items()}
        return cls(merges, vocab)


def _merge(ids: list[int], pair: tuple[int, int], new_id: int) -> list[int]:
    """Replace every occurrence of `pair` in `ids` with `new_id`."""
    out: list[int] = []
    i = 0
    while i < len(ids):
        if i < len(ids) - 1 and ids[i] == pair[0] and ids[i + 1] == pair[1]:
            out.append(new_id)
            i += 2
        else:
            out.append(ids[i])
            i += 1
    return out
