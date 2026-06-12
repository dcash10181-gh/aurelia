"""BPE tokenizer: round-trip, compression, persistence, byte-safety."""
from aurelia_mini_llm.bpe import BPETokenizer


def test_roundtrip_is_lossless():
    tok = BPETokenizer.train("the agent runs locally on your machine. " * 50,
                             vocab_size=300)
    for s in ["the agent", "your machine", "locally", "unseen WORDS 123!"]:
        assert tok.decode(tok.encode(s)) == s


def test_merges_compress():
    text = "the system processes the request carefully. " * 100
    tok = BPETokenizer.train(text, vocab_size=400)
    # After merges, a repeated phrase encodes to far fewer tokens than bytes.
    phrase = "the system processes the request"
    assert len(tok.encode(phrase)) < len(phrase.encode("utf-8"))


def test_byte_level_has_no_oov():
    # Trained on ASCII, must still encode arbitrary UTF-8 (emoji, accents).
    tok = BPETokenizer.train("plain ascii text only", vocab_size=300)
    for s in ["café", "naïve", "日本語", "emoji 🚀 ok"]:
        assert tok.decode(tok.encode(s)) == s


def test_save_load_round_trip(tmp_path):
    tok = BPETokenizer.train("aurelia is a local first agent " * 40,
                             vocab_size=320)
    p = tmp_path / "bpe.json"
    tok.save(p)
    loaded = BPETokenizer.load(p)
    assert loaded.vocab_size == tok.vocab_size
    s = "aurelia is local"
    assert loaded.encode(s) == tok.encode(s)
    assert loaded.decode(loaded.encode(s)) == s


def test_min_vocab_is_byte_floor():
    tok = BPETokenizer.train("x", vocab_size=256)
    assert tok.vocab_size == 256  # no merges, pure byte vocab
