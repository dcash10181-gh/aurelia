"""Training loop for the mini LLM.

Usage:
    python -m aurelia_mini_llm.train [--steps 300] [--out ~/.aurelia/mini_llm.pt]
Runs on CPU in well under a minute with default settings.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import torch

from .config import DEFAULT_CKPT, MiniConfig
from .dataset import get_batch, load_corpus
from .model import MiniGPT
from .tokenizer import CharTokenizer


def train(cfg: MiniConfig | None = None, data_path: str | None = None,
          out_path: str | Path | None = None, log_every: int = 50) -> Path:
    cfg = cfg or MiniConfig()
    torch.manual_seed(cfg.seed)

    text = load_corpus(data_path)
    tok = CharTokenizer.from_text(text)
    cfg.vocab_size = tok.vocab_size
    data = torch.tensor(tok.encode(text), dtype=torch.long)

    model = MiniGPT(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"mini-llm: vocab={cfg.vocab_size} params={n_params:,} steps={cfg.max_steps}")

    model.train()
    t0 = time.time()
    for step in range(cfg.max_steps):
        x, y = get_batch(data, cfg.block_size, cfg.batch_size)
        _, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        if step % log_every == 0 or step == cfg.max_steps - 1:
            print(f"step {step:4d}  loss {loss.item():.3f}  ({time.time()-t0:.1f}s)")

    out = Path(out_path or DEFAULT_CKPT)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"config": cfg.__dict__, "model": model.state_dict(),
                "stoi": tok.stoi}, out)
    print(f"saved checkpoint -> {out}")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Train the AURELIA mini LLM")
    p.add_argument("--steps", type=int, default=300)
    p.add_argument("--data", type=str, default=None)
    p.add_argument("--out", type=str, default=None)
    a = p.parse_args()
    cfg = MiniConfig(max_steps=a.steps)
    train(cfg, data_path=a.data, out_path=a.out)


if __name__ == "__main__":
    main()
