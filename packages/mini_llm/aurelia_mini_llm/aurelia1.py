"""AURELIA-1 training and inference (BPE tokenizer, ~7M params).

Separate entry point from the char-level mini LLM so both models coexist and
are independently selectable in the UI. Same MiniGPT architecture (it is
generic over the config), larger config, BPE tokenizer, real corpus.

Honesty, unchanged from the mini model: this is an educational from-scratch
LM. With BPE and a 400KB corpus it produces word-like, grammatical-looking
English, but it is NOT factual or intelligent. Every surface that exposes it
says so; for real local intelligence the user selects an Ollama model.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import torch

from .bpe import BPETokenizer
from .config import AURELIA1_CKPT, AURELIA1_DATA, Aurelia1Config
from .dataset import get_batch
from .model import MiniGPT

DISCLAIMER = ("\n\n— AURELIA-1 (from-scratch educational model; word-like but "
              "not factual or intelligent)")


def train(cfg: Aurelia1Config | None = None, data_path: str | None = None,
          out_path: str | Path | None = None, log_every: int = 100) -> Path:
    cfg = cfg or Aurelia1Config()
    torch.manual_seed(cfg.seed)

    text = Path(data_path or AURELIA1_DATA).read_text(encoding="utf-8")
    print("training BPE tokenizer...")
    tok = BPETokenizer.train(text, vocab_size=cfg.bpe_vocab_size)
    cfg.vocab_size = tok.vocab_size
    data = torch.tensor(tok.encode(text), dtype=torch.long)
    print(f"corpus: {len(text):,} chars -> {len(data):,} tokens "
          f"({len(text)/len(data):.1f} chars/token)")

    model = MiniGPT(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"aurelia-1: vocab={cfg.vocab_size} params={n_params:,} steps={cfg.max_steps}")

    model.train()
    t0 = time.time()
    for step in range(cfg.max_steps):
        x, y = get_batch(data, cfg.block_size, cfg.batch_size)
        _, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step % log_every == 0 or step == cfg.max_steps - 1:
            print(f"step {step:5d}  loss {loss.item():.3f}  ({time.time()-t0:.1f}s)")

    out = Path(out_path or AURELIA1_CKPT)
    out.parent.mkdir(parents=True, exist_ok=True)
    blob = {
        "kind": "aurelia1",
        "config": cfg.__dict__,
        "model": model.state_dict(),
        "bpe": {
            "merges": [list(p) for p in tok.merges],
            "vocab": {str(k): list(v) for k, v in tok.vocab.items()},
        },
    }
    torch.save(blob, out)
    print(f"saved checkpoint -> {out}")
    return out


def _load(checkpoint: str | Path | None):
    path = Path(checkpoint or AURELIA1_CKPT)
    if not path.exists():
        raise FileNotFoundError(
            f"No AURELIA-1 checkpoint at {path}. Train first: "
            "`aurelia train-aurelia1`")
    blob = torch.load(path, map_location="cpu", weights_only=False)
    cfg = Aurelia1Config(**blob["config"])
    merges = [tuple(p) for p in blob["bpe"]["merges"]]
    vocab = {int(k): bytes(v) for k, v in blob["bpe"]["vocab"].items()}
    tok = BPETokenizer(merges, vocab)
    model = MiniGPT(cfg)
    model.load_state_dict(blob["model"])
    model.eval()
    return model, tok, cfg


def load_generator(checkpoint: str | Path | None = None, max_new_tokens: int = 80):
    model, tok, cfg = _load(checkpoint)

    def generate(prompt: str) -> str:
        ids = tok.encode(prompt) or [0]
        idx = torch.tensor([ids[-cfg.block_size:]], dtype=torch.long)
        out = model.generate(idx, max_new_tokens=max_new_tokens)
        return tok.decode(out[0].tolist())

    return generate


def load_stream_generator(checkpoint: str | Path | None = None,
                          max_new_tokens: int = 100):
    model, tok, cfg = _load(checkpoint)

    def stream(prompt: str):
        ids = tok.encode(prompt) or [0]
        idx = torch.tensor([ids[-cfg.block_size:]], dtype=torch.long)
        # BPE: one token may decode to multiple bytes; buffer until a full
        # UTF-8 sequence is available so we never emit a broken character.
        buf: list[int] = []
        for token_id in model.stream_generate(idx, max_new_tokens=max_new_tokens):
            buf.append(token_id)
            piece = tok.decode(buf)
            if "\ufffd" not in piece:  # complete, valid decode
                yield piece
                buf = []

    return stream


def main() -> None:
    ap = argparse.ArgumentParser(description="Train AURELIA-1")
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()
    cfg = Aurelia1Config()
    if args.steps:
        cfg.max_steps = args.steps
    train(cfg, out_path=args.out)
    print("Done. Try: aurelia generate --model aurelia1 --prompt 'the agent '")


if __name__ == "__main__":
    main()
