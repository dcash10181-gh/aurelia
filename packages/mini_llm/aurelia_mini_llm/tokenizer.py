"""Character-level tokenizer.

Decision: character-level instead of BPE. The corpus is ~4 KB; a learned
subword vocabulary would be noise. Character tokens keep the entire pipeline
inspectable in one screen of code, which is the point of this package.
"""
from __future__ import annotations

import json
from pathlib import Path


class CharTokenizer:
    def __init__(self, stoi: dict[str, int]):
        self.stoi = stoi
        self.itos = {i: s for s, i in stoi.items()}

    @classmethod
    def from_text(cls, text: str) -> "CharTokenizer":
        chars = sorted(set(text))
        return cls({ch: i for i, ch in enumerate(chars)})

    @property
    def vocab_size(self) -> int:
        return len(self.stoi)

    def encode(self, text: str) -> list[int]:
        # Unknown characters are skipped rather than crashing generation.
        return [self.stoi[c] for c in text if c in self.stoi]

    def decode(self, ids: list[int]) -> str:
        return "".join(self.itos.get(i, "") for i in ids)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.stoi), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "CharTokenizer":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))
