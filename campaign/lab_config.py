"""Private deployment configuration; never commit .local/config.json."""
import json, os, sys
from pathlib import Path
from datetime import datetime, timezone
REPO = Path(__file__).resolve().parent.parent

def config():
    path = Path(os.environ.get("FV_LAB_CONFIG", str(REPO / ".local/config.json")))
    return json.loads(path.read_text())

def require_execute():
    if "--execute" not in sys.argv:
        raise SystemExit("Live campaign disabled. Supply --execute and private FV_LAB_CONFIG.")
    cfg = config()
    stop = datetime.fromisoformat(cfg["stop_at"])
    if stop.tzinfo is None or stop <= datetime.now(timezone.utc):
        raise SystemExit("A future, timezone-aware spending deadline is required.")
    os.umask(0o077)
    return cfg

def credential(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(name + " must be provided privately to this process")
    return value
