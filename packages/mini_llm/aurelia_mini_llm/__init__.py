"""aurelia_mini_llm — an educational, from-scratch character-level transformer.

This is intentionally tiny (~0.2M parameters by default). It demonstrates the
full LM pipeline — tokenize → train → checkpoint → sample — on a CPU in
seconds. It is NOT intelligent, factual, or production-grade. For real
generative quality, connect AURELIA to a local runtime such as Ollama
(see docs/local_models.md).
"""
__version__ = "0.1.0"
