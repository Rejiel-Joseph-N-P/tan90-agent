import subprocess, time, os, urllib.request

ALLOWED = {"tan90-app", "tan90-postgres", "tan90-jellyfin", "tan90-nginx"}
TAN90_URL = os.environ.get("TAN90_URL", "http://localhost")

def _run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=timeout)
        return r.stdout.strip()[:4000] or "(no output)"
    except Exception as e:
        return f"error: {e}"

def list_containers():
    return _run(["docker", "ps", "-a", "--filter", "name=tan90-",
                 "--format", "{{.Names}}\t{{.Status}}"])

def container_logs(name, lines=50):
    if name not in ALLOWED:
        return f"error: '{name}' not allowed. Choose from {sorted(ALLOWED)}"
    lines = max(1, min(int(lines), 200))
    return _run(["docker", "logs", "--tail", str(lines), name])

def disk_usage():
    return _run(["df", "-h"] + [d for d in ("/", "/opt/ai") if os.path.exists(d)]) + "\n" + _run(["zpool", "list"])

def memory_usage():
    return _run(["free", "-m"])

def db_check():
    return _run(["docker", "exec", "tan90-postgres", "pg_isready"])

def http_check():
    t = time.time()
    try:
        with urllib.request.urlopen(TAN90_URL, timeout=8) as r:
            return f"{TAN90_URL} -> HTTP {r.status} in {int((time.time()-t)*1000)} ms"
    except Exception as e:
        return f"{TAN90_URL} unreachable: {e}"

REGISTRY = {f.__name__: f for f in
            [list_containers, container_logs, disk_usage, memory_usage, db_check, http_check]}

def _tool(name, desc, props=None, req=None):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props or {}, "required": req or []}}}

SCHEMAS = [
    _tool("list_containers", "List tan90 Docker containers and their status."),
    _tool("container_logs", "Get recent log lines from a tan90 container.",
          {"name": {"type": "string", "description": "tan90-app, tan90-postgres, tan90-jellyfin or tan90-nginx"},
           "lines": {"type": "integer"}}, ["name"]),
    _tool("disk_usage", "Disk usage for system disk, AI storage and ZFS pool."),
    _tool("memory_usage", "RAM and swap usage of the server."),
    _tool("db_check", "Check whether the tan90 PostgreSQL database accepts connections."),
    _tool("http_check", "Check that the tan90 web app responds over HTTP."),
]
