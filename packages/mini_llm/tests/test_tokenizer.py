from aurelia_mini_llm.tokenizer import CharTokenizer


def test_roundtrip():
    tok = CharTokenizer.from_text("hello world")
    ids = tok.encode("hello")
    assert tok.decode(ids) == "hello"
    assert tok.vocab_size == len(set("hello world"))


def test_unknown_chars_skipped():
    tok = CharTokenizer.from_text("abc")
    assert tok.decode(tok.encode("aZb")) == "ab"


def test_save_load(tmp_path):
    tok = CharTokenizer.from_text("aurelia")
    p = tmp_path / "vocab.json"
    tok.save(p)
    tok2 = CharTokenizer.load(p)
    assert tok2.stoi == tok.stoi
