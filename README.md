# tan90-agent

A small, read-only ops agent for my self-hosted streaming platform, tan90.
It runs a local LLM (Ollama, qwen2.5:3b) in a tool-calling loop on my home Ubuntu server.

## How it works
question -> LLM -> tool call -> result -> LLM -> ... -> final answer

- `agent.py`: the loop (max 6 steps, duplicate-call protection, forced final answer)
- `tools.py`: an allowlist of six read-only tools: container status, container logs, disk, RAM, Postgres check, HTTP check
- Every step is logged to `logs/agent.jsonl`
- `python3 agent.py --report` runs all checks deterministically, then the LLM summarizes them

## Design notes
- No arbitrary shell: the model can only call the functions in `tools.py`
- Small CPU-only models call tools inconsistently, so the report mode does not rely on the model to choose what to check
- Hardware: Intel i5-3330, ~10GB RAM, no GPU

## Run
    export OLLAMA_URL=http://localhost:11434 AGENT_MODEL=qwen2.5:3b TAN90_URL=http://localhost
    python3 agent.py "Are all tan90 containers healthy?"
    python3 agent.py --report

See `docs/` for sample output.
