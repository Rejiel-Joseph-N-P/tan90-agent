import json, os, sys, time, urllib.request
from tools import REGISTRY, SCHEMAS

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("AGENT_MODEL", "qwen2.5:1.5b")
MAX_STEPS = 6
LOG = os.path.join(os.path.dirname(__file__), "logs", "agent.jsonl")

SYSTEM = ("You are the ops agent for tan90, a self-hosted video streaming platform. "
          "Always respond by calling tools first, starting with list_containers; never describe what you plan to do. "
          "You are read-only. Finish with a short summary and any suggested fix.")

def log(event, **data):
    with open(LOG, "a") as f:
        f.write(json.dumps({"ts": time.time(), "event": event, **data}) + "\n")

def chat(messages, use_tools=True):
    body = json.dumps({"model": MODEL, "messages": messages, "tools": SCHEMAS if use_tools else [],
                       "stream": False,
                       "options": {"temperature": 0, "num_ctx": 4096}}).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", body,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.load(r)["message"]

def run(question):
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    log("question", text=question)
    seen, force_final = set(), False
    for step in range(MAX_STEPS):
        msg = chat(messages, use_tools=(step < MAX_STEPS - 1 and not force_final))
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            if step < 2 and not any(m.get("role") == "tool" for m in messages):
                messages.append({"role": "user", "content": "Do not describe a plan. Call a tool now."})
                log("nudge", step=step)
                continue
            log("answer", text=msg.get("content"))
            return msg.get("content", "")
        executed = 0
        for c in calls[:4]:
            name, args = c["function"]["name"], c["function"].get("arguments", {})
            key = (name, json.dumps(args, sort_keys=True))
            if key in seen:
                continue
            seen.add(key)
            executed += 1
            fn = REGISTRY.get(name)
            try:
                result = fn(**args) if fn else f"error: unknown tool {name}"
            except Exception as e:
                result = f"error: {e}"
            result = result[:1500]
            log("tool_call", step=step, tool=name, args=args, result=result[:500])
            print(f"[step {step+1}] {name}({args})")
            messages.append({"role": "tool", "tool_name": name, "content": result})
        if executed == 0:
            messages.append({"role": "user", "content": "You already have those results. Write the final summary now."})
            force_final = True
    return "Stopped: step limit reached."

def report():
    from tools import (list_containers, memory_usage, disk_usage,
                       db_check, http_check, container_logs)
    data = {"containers": list_containers(), "memory": memory_usage(),
            "disk": disk_usage(), "database": db_check(), "http": http_check(),
            "app_log_tail": container_logs("tan90-app", 20)}
    for k, v in data.items():
        log("tool_call", tool=k, result=v[:500])
    body = "\n\n".join(f"## {k}\n{v[:1200]}" for k, v in data.items())
    prompt = ("Summarize the health of tan90 from this data. Flag anything abnormal "
              "(stopped containers, high RAM or disk use, errors in logs, failed checks). Be brief. Only state facts that appear verbatim in the data; do not guess ports, causes or states. If unsure, say so. Log lines are in chronological order; the last line is the most recent.\n\n" + body)
    msg = chat([{"role": "system", "content": "You are a concise server ops assistant."},
                {"role": "user", "content": prompt}], use_tools=False)
    log("answer", text=msg.get("content"))
    return "RAW CHECKS\n" + body + "\n\nLLM SUMMARY (model-generated, verify against raw checks)\n" + msg.get("content", "")

if __name__ == "__main__":
    if sys.argv[1:] == ["--report"]:
        print("\n" + report())
    elif len(sys.argv) > 1:
        print("\n" + run(" ".join(sys.argv[1:])))
    else:
        while True:
            q = input("\ntan90-agent> ").strip()
            if q in ("exit", "quit"): break
            if q: print("\n" + run(q))
