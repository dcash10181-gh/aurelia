"""AURELIA-1 train→save→load→generate pipeline (tiny config for speed)."""
from aurelia_mini_llm.aurelia1 import (
    load_generator, load_stream_generator, train)
from aurelia_mini_llm.config import Aurelia1Config


def test_pipeline_end_to_end(tmp_path):
    ckpt = tmp_path / "a1.pt"
    cfg = Aurelia1Config(n_layer=2, n_embd=48, block_size=24,
                         max_steps=40, bpe_vocab_size=320)
    train(cfg, out_path=ckpt, log_every=20)
    assert ckpt.exists()

    gen = load_generator(ckpt)
    out = gen("the ")
    assert isinstance(out, str) and len(out) > 0

    stream = load_stream_generator(ckpt)
    pieces = list(stream("a "))
    # Every streamed piece must be valid text (UTF-8 buffering, no replacement char)
    joined = "".join(pieces)
    assert "\ufffd" not in joined


def test_missing_checkpoint_is_actionable(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError, match="train-aurelia1"):
        load_generator(tmp_path / "nope.pt")
