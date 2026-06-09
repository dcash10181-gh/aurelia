"""Smoke test: a real (tiny) train run reduces loss and a checkpoint generates."""
import torch

from aurelia_mini_llm.config import MiniConfig
from aurelia_mini_llm.generate import load_generator
from aurelia_mini_llm.train import train


def test_train_and_generate(tmp_path):
    cfg = MiniConfig(max_steps=30, block_size=32, n_layer=1, n_head=2,
                     n_embd=32, batch_size=8)
    ckpt = train(cfg, out_path=tmp_path / "ckpt.pt", log_every=1000)
    assert ckpt.exists()
    gen = load_generator(ckpt, max_new_tokens=20)
    out = gen("aurelia ")
    assert isinstance(out, str) and len(out) > len("aurelia ")


def test_training_step_reduces_loss():
    torch.manual_seed(0)
    from aurelia_mini_llm.dataset import get_batch, load_corpus
    from aurelia_mini_llm.model import MiniGPT
    from aurelia_mini_llm.tokenizer import CharTokenizer

    text = load_corpus()
    tok = CharTokenizer.from_text(text)
    cfg = MiniConfig(max_steps=0, block_size=32, n_layer=1, n_head=2, n_embd=32,
                     vocab_size=tok.vocab_size, dropout=0.0)
    data = torch.tensor(tok.encode(text), dtype=torch.long)
    model = MiniGPT(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3)
    x, y = get_batch(data, cfg.block_size, 8)
    _, loss0 = model(x, y)
    for _ in range(20):
        xb, yb = get_batch(data, cfg.block_size, 8)
        _, loss = model(xb, yb)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
    _, loss1 = model(x, y)
    assert loss1.item() < loss0.item()


def test_stream_generate_matches_batch_shape(tmp_path):
    """stream_generate yields exactly max_new_tokens ids; generate() (which
    wraps it) returns prompt + that many tokens."""
    import torch
    from aurelia_mini_llm.config import MiniConfig
    from aurelia_mini_llm.model import MiniGPT

    cfg = MiniConfig(vocab_size=20, block_size=16, n_layer=1, n_head=2, n_embd=16)
    model = MiniGPT(cfg)
    idx = torch.zeros((1, 4), dtype=torch.long)

    streamed = list(model.stream_generate(idx, max_new_tokens=7))
    assert len(streamed) == 7
    assert all(isinstance(t, int) and 0 <= t < cfg.vocab_size for t in streamed)

    out = model.generate(idx, max_new_tokens=7)
    assert out.shape == (1, 4 + 7)
