import torch

from aurelia_mini_llm.config import MiniConfig
from aurelia_mini_llm.model import MiniGPT


def _cfg():
    return MiniConfig(block_size=16, n_layer=1, n_head=2, n_embd=16,
                      vocab_size=20, dropout=0.0)


def test_forward_shapes():
    cfg = _cfg()
    model = MiniGPT(cfg)
    x = torch.randint(0, cfg.vocab_size, (3, 10))
    logits, loss = model(x)
    assert logits.shape == (3, 10, cfg.vocab_size)
    assert loss is None


def test_loss_and_backward():
    cfg = _cfg()
    model = MiniGPT(cfg)
    x = torch.randint(0, cfg.vocab_size, (2, 8))
    y = torch.randint(0, cfg.vocab_size, (2, 8))
    _, loss = model(x, y)
    assert loss is not None and loss.item() > 0
    loss.backward()  # gradients flow


def test_generation_extends_sequence():
    cfg = _cfg()
    model = MiniGPT(cfg)
    idx = torch.zeros((1, 4), dtype=torch.long)
    out = model.generate(idx, max_new_tokens=12)
    assert out.shape == (1, 16)
    assert int(out.max()) < cfg.vocab_size
