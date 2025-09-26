# apps/api/server.py
from pathlib import Path
from datetime import datetime, timedelta
import csv, json, time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
EVENTS_CSV = DATA_DIR / "events.csv"
FIELDS = ["iso_ts", "source", "type", "app", "note"]

app = FastAPI(title="FocusAir Phone Events")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

def append_event(row: dict):
    exists = EVENTS_CSV.exists()
    with open(EVENTS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists: w.writeheader()
        w.writerow(row)

def try_parse_json_field(x):
    if not isinstance(x, str): return None
    s = x.strip()
    if not s or (s[0] not in "{[" and not s.startswith('"{')):
        return None
    try:
        return json.loads(s)
    except Exception:
        return None

# in-memory dedupe cache
_last_seen = {}  # key -> last_ts (unix)
DEDUP_SECONDS = 10

@app.get("/")
def root():
    return {"ok": True, "events_csv": str(EVENTS_CSV)}

@app.get("/test")
def test():
    row = {"iso_ts": datetime.now().isoformat(timespec="seconds"),
           "source":"browser","type":"test_ping","app":"","note":"manual"}
    append_event(row); return {"ok": True, "saved": row}

@app.api_route("/phone/event", methods=["GET","POST"])
async def phone_event(req: Request):
    # 1) pull data from JSON, form, or query string
    data = {}
    try:
        data = await req.json()
    except Exception:
        try:
            form = await req.form()
            data = dict(form)
        except Exception:
            data = {}
    qs = parse_qs(urlparse(str(req.url)).query)
    for k, v in qs.items():
        if v and k not in data: data[k] = v[0]

    # 2) if fields themselves contain a JSON blob, parse it
    for k in list(data.keys()):
        parsed = try_parse_json_field(data.get(k))
        if isinstance(parsed, dict):
            # merge parsed keys (source/type/app/note) into data
            for kk, vv in parsed.items():
                data.setdefault(kk, vv)

    # 3) normalize fields
    source = str(data.get("source", "unknown")).lower().strip()
    etype  = str(data.get("type", "unknown")).lower().strip()
    app    = str(data.get("app", "")).lower().strip()
    note   = str(data.get("note", "")).strip()

    # if an app is present but type looks like unlock -> treat as app_open
    if app and etype in ("unlock", "unknown", ""):
        etype = "app_open"

    # 4) dedupe identical (source, type, app) for a short window
    now_dt = datetime.now()
    key = f"{source}|{etype}|{app}"
    now_unix = time.time()
    last = _last_seen.get(key, 0.0)
    if now_unix - last < DEDUP_SECONDS:
        return JSONResponse({"ok": True, "skipped": "dedup", "saved": {
            "iso_ts": now_dt.isoformat(timespec="seconds"),
            "source": source, "type": etype, "app": app, "note": note
        }})

    _last_seen[key] = now_unix

    row = {"iso_ts": now_dt.isoformat(timespec="seconds"),
           "source": source, "type": etype, "app": app, "note": note}
    append_event(row)
    return JSONResponse({"ok": True, "saved": row})
