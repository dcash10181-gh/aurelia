# Plugin / Tool API

A tool is a named function: `dict args -> str result`. Register it once and
it appears in the REST API, the UI tools panel, the CLI, and the agent loop.

## Add a tool in 4 steps
1. Write the handler (raise exceptions for errors; they become HTTP 400):

```python
# services/api/aurelia_api/tools/weather_stub.py
def weather(args: dict) -> str:
    city = str(args.get("city", "")).strip()
    if not city:
        raise ValueError("Missing 'city'")
    return f"(stub) Weather for {city}: look outside — AURELIA is offline-first."
```

2. Register it in `build_default_registry` (`tools/builtin.py`):

```python
from .weather_stub import weather
reg.register(Tool("weather", "Stub weather lookup.", weather,
                  {"city": "string — city name"}))
```

3. Add a test:

```python
def test_weather_tool(client):
    r = client.post("/api/tools/invoke",
                    json={"name": "weather", "args": {"city": "Austin"}})
    assert r.status_code == 200
```

4. Run `./scripts/test_all.sh`.

## Rules
- **Sandbox filesystem access** to the data directory (copy the `NotesTool`
  `_safe_path` pattern).
- **Never use eval/exec**; parse inputs explicitly.
- Anything that executes code or touches the network must default to
  `enabled=False` with an explicit env flag, like the shell tool.
- Keep handlers synchronous and fast (<1s) or run work in a thread; the agent
  loop is synchronous by design.

## Agent routing (optional)
To let natural language trigger your tool, add an intent pattern in
`agent/loop.py`. Keep patterns conservative — false positives are worse than
falling through to the model provider.
