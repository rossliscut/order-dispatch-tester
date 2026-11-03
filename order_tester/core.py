# -*- coding: utf-8 -*-
"""Dispatcher-neutral core: settings, templates, drafts, batches, polling, stuck detection.
All dispatcher I/O goes through ``S["adapter"]`` (see adapters/base.py)."""
import copy, datetime, io, json, math, os, random, shutil, sys, threading, time, uuid, zipfile
from . import templates as T
from .adapters import get_adapter, ADAPTERS
from .adapters import rds_scene
from . import i18n

lock = threading.RLock()
DRAFT = "待下发"            # draft state value (kept as-is for compatibility with existing drafts.json/sent_orders.json)
MOVE_EPS_M = 0.05           # vehicle moved more than this (m) -> order counts as changed
MOVE_EPS_DEG = 2.0          # heading changed more than this (deg) -> order counts as changed
MOVE_LOG_SEC = 30           # order_move log throttle per order
HIST_GAP_SEC = 900          # legacy orders without batch: new group if send gap > this
HIST_CREATED_SEC = 60       # ... or created differs by more than this

S = {"running": False, "sent": 0, "cfg": {}, "orders": {}, "robots": {}, "robots_raw": None, "msg": "", "prepoints": {}, "geom": None,
     "groups": [], "robot_group": {}, "groups_try": 0, "odcache": {}, "opos": {}, "omovelog": {}, "adapter": None}
P = {}  # paths

def init(data_dir, adapter="rds", base="http://127.0.0.1:8088"):
    P["data"] = os.path.abspath(data_dir); os.makedirs(P["data"], exist_ok=True)
    P["logs"] = os.path.join(P["data"], "logs"); os.makedirs(P["logs"], exist_ok=True)
    P["settings"] = os.path.join(P["data"], "settings.json")
    P["drafts"] = os.path.join(P["data"], "drafts.json")
    P["sent"] = os.path.join(P["data"], "sent_orders.json")
    P["smap_cache"] = os.path.join(P["data"], "pointcloud_cache.json")
    P["maps"] = os.path.join(P["data"], "maps")
    P["scene_cache"] = os.path.join(P["data"], "scene_cache.json")
    P["log"] = os.path.join(P["logs"], "rds_%s.jsonl" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    P["templates"] = os.path.join(P["data"], "templates"); os.makedirs(P["templates"], exist_ok=True)
    S["store"] = T.Store(P["templates"])  # rebound to templates/<serverId>/ after migrate / select
    S["adapter"] = get_adapter(adapter, base, log)
    restore_scene_cache()

def AD(): return S["adapter"]
def TERMINAL(): return AD().terminal_states
def msg(key, **kw): return i18n.t(load_settings().get("lang") or "zh", key, **kw)

# ---------------------------------------------------------------- settings
# Per-dispatcher-server persistence. File shape (v2):
#   { "version": 2, "lang": "zh", "currentServerId": "<id>",
#     "servers": [ { "id", "name", "base", "adapter", "pollSec", "fields", "pools",
#                    "activeTemplate", "strategy", "pm", "smapPath", "smapAuto",
#                    "smapAutoHash", "vsPerBlock", "m4": {active, profiles} }, ... ] }
# load_settings() returns a flat view of the current server (+ lang / currentServerId / servers)
# so existing callers keep working. save_settings() routes keys into the current server bucket
# (except GLOBAL_KEYS). Secrets (M4 appKey/password) are never logged.

GLOBAL_KEYS = frozenset({"lang", "version", "currentServerId", "servers"})
SERVER_KEYS = frozenset({
    "name", "base", "adapter", "pollSec", "fields", "pools", "starts", "ends",
    "activeTemplate", "strategy", "pm", "pmPool", "smapPath", "smapAuto", "smapAutoHash",
    "vsPerBlock", "vsBlocks", "m4",
})
DEFAULT_BASE = "http://127.0.0.1:8088"

def normalize_base(url):
    """strip whitespace and trailing slash; empty stays empty"""
    if not isinstance(url, str): return ""
    u = url.strip()
    while u.endswith("/"): u = u[:-1]
    return u

def _m4_active_base(srv):
    """URL from the active (or first) M4 profile when server.base is empty."""
    m = srv.get("m4") if isinstance(srv, dict) else None
    m = m if isinstance(m, dict) else {}
    profs = m.get("profiles") if isinstance(m.get("profiles"), dict) else {}
    if not profs: return ""
    act = m.get("active") or ""
    p = profs.get(act) if act in profs else None
    if not isinstance(p, dict):
        p = next(iter(profs.values()), None)
    if not isinstance(p, dict): return ""
    return normalize_base(p.get("base") or "")

def _new_server_id():
    return "srv-" + uuid.uuid4().hex[:10]

def _host_label(base):
    try:
        from urllib.parse import urlparse
        h = urlparse(base if "://" in base else "http://" + base).hostname
        if h: return h
    except Exception: pass
    return ""

def default_server(base=None, name=None, adapter="rds"):
    b = normalize_base(base or DEFAULT_BASE) or DEFAULT_BASE
    return {
        "id": _new_server_id(),
        "name": name or _host_label(b) or "默认",
        "base": b,
        "adapter": adapter or "rds",
        "pollSec": 2,
        "fields": {},
        "pools": {"start": [], "end": []},
        "activeTemplate": "",
        "strategy": "random",
        "pm": "start",
        "m4": {"active": "default", "profiles": {}},
    }

def _read_raw():
    try:
        with open(P["settings"], encoding="utf-8") as f: d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception: return {}

def _write_raw(d):
    tmp = P["settings"] + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, P["settings"])

def _is_v2(raw):
    return isinstance(raw.get("servers"), list)

def _flatten(raw, srv=None):
    """flat view: current server fields + global lang/currentServerId + servers summary"""
    if not isinstance(raw, dict): raw = {}
    servers = raw.get("servers") if isinstance(raw.get("servers"), list) else []
    sid = raw.get("currentServerId")
    if srv is None:
        srv = next((s for s in servers if isinstance(s, dict) and s.get("id") == sid), None)
        if srv is None and servers:
            srv = next((s for s in servers if isinstance(s, dict)), None)
    out = {}
    if isinstance(srv, dict):
        for k, v in srv.items():
            if k == "id": continue
            if k == "pools" and isinstance(v, dict):
                out[k] = normalize_pools(v)
            else:
                out[k] = copy.deepcopy(v)
        out["id"] = srv.get("id")
    out["lang"] = raw.get("lang") or "zh"
    out["currentServerId"] = (srv or {}).get("id") or sid
    out["version"] = raw.get("version") or 2
    # lightweight list for UI (no secrets); M4 falls back to active profile base when server.base is blank
    out["servers"] = []
    for s in servers:
        if not isinstance(s, dict) or not s.get("id"): continue
        base = s.get("base") or ""
        if not base and (s.get("adapter") or "rds") == "m4":
            base = _m4_active_base(s)
        out["servers"].append({"id": s.get("id"), "name": s.get("name") or "", "base": base or "", "adapter": s.get("adapter") or "rds"})
    return out

def load_settings():
    raw = _read_raw()
    if not raw: return {}
    if _is_v2(raw): return _flatten(raw)
    # pre-migration flat file: return as-is (migrate_servers will rewrite)
    return raw

def _ensure_v2_unlocked(raw=None):
    """ensure raw is v2 with at least one server; does not write. Caller holds lock if writing."""
    raw = dict(raw if raw is not None else _read_raw())
    if not _is_v2(raw):
        # treat as flat; caller should have migrated. synthesize ephemeral.
        srv = default_server(raw.get("base"), name="默认", adapter=raw.get("adapter") or "rds")
        for k in SERVER_KEYS:
            if k in raw and k not in ("name",): srv[k] = copy.deepcopy(raw[k])
        if isinstance(raw.get("m4"), dict): srv["m4"] = copy.deepcopy(raw["m4"])
        raw = {"version": 2, "lang": raw.get("lang") or "zh", "currentServerId": srv["id"], "servers": [srv]}
    servers = [s for s in (raw.get("servers") or []) if isinstance(s, dict)]
    if not servers:
        srv = default_server()
        raw["servers"] = [srv]
        raw["currentServerId"] = srv["id"]
        servers = [srv]
    sid = raw.get("currentServerId")
    if not any(s.get("id") == sid for s in servers):
        raw["currentServerId"] = servers[0]["id"]
    raw["version"] = 2
    raw.setdefault("lang", "zh")
    return raw

def current_server(raw=None):
    raw = _ensure_v2_unlocked(raw)
    sid = raw.get("currentServerId")
    for s in raw["servers"]:
        if s.get("id") == sid: return s, raw
    return raw["servers"][0], raw

def save_settings(part):
    """merge into settings.json: global keys at top level; other keys into the current server bucket"""
    if not isinstance(part, dict) or not part: return
    with lock:
        raw = _ensure_v2_unlocked()
        # apply global
        if "lang" in part and part["lang"]:
            raw["lang"] = part["lang"]
        if "currentServerId" in part and part["currentServerId"]:
            if any(s.get("id") == part["currentServerId"] for s in raw["servers"]):
                raw["currentServerId"] = part["currentServerId"]
        srv, raw = current_server(raw)
        for k, v in part.items():
            if k in GLOBAL_KEYS: continue
            if k == "id": continue
            if k == "base" and isinstance(v, str): v = normalize_base(v)
            if k == "pools" and isinstance(v, dict): v = normalize_pools(v)
            if k in ("starts", "ends") and isinstance(v, list):
                v = [T.entry_station(x) for x in v if T.entry_station(x)]
            if isinstance(v, dict) and isinstance(srv.get(k), dict) and k not in ("pools", "pmPool"):
                srv[k] = dict(srv.get(k) or {}); srv[k].update(v)
            else:
                srv[k] = v
        # keep top-level servers list in sync
        for i, s in enumerate(raw["servers"]):
            if s.get("id") == srv.get("id"):
                raw["servers"][i] = srv
                break
        _write_raw(raw)

def servers_list():
    raw = _read_raw()
    if not _is_v2(raw):
        raw = _ensure_v2_unlocked(raw if raw else {})
    else:
        raw = _ensure_v2_unlocked(raw)
    flat = _flatten(raw)
    return {"servers": flat["servers"], "currentServerId": flat["currentServerId"], "lang": flat.get("lang") or "zh"}

def add_server(name=None, base=None, adapter=None, activate=True):
    """Create a new server with empty connection fields / pools / scene.
    Seeds that server's template store with T.builtin_default() and sets activeTemplate
    to its name (usually "default"). Does not re-seed later if the user clears templates.
    Name is required (non-empty after strip); returns None if missing.
    Does not copy the current form URL; pass base only when the caller supplies one.
    Adapter is always RDS for new servers (adapter arg ignored); user may change later
    via /api/adapter. Drafts/sent/scene stay empty until the user fills them."""
    name = (name or "").strip()
    if not name:
        return None
    with lock:
        raw = _ensure_v2_unlocked()
        ad = "rds"  # never inherit previous (e.g. M4); user changes later if needed
        explicit = normalize_base(base) if (isinstance(base, str) and base.strip()) else ""
        # scaffold via default_server then blank the URL unless explicitly provided
        srv = default_server(explicit or DEFAULT_BASE, name=name, adapter=ad)
        srv["name"] = name
        if not explicit:
            srv["base"] = ""
        # per-server template folder + seed builtin default (once at create)
        td = templates_dir(srv["id"])
        try: os.makedirs(td, exist_ok=True)
        except Exception: pass
        t = T.builtin_default()
        try:
            T.Store(td).put(t)
            srv["activeTemplate"] = t.get("name") or "default"
        except Exception:
            srv["activeTemplate"] = ""
        raw["servers"].append(srv)
        if activate: raw["currentServerId"] = srv["id"]
        _write_raw(raw)
        return srv["id"]


def rename_server(sid, name):
    name = (name or "").strip()
    if not name: return False
    with lock:
        raw = _ensure_v2_unlocked()
        for s in raw["servers"]:
            if s.get("id") == sid:
                s["name"] = name
                _write_raw(raw)
                return True
        return False

def delete_server(sid):
    with lock:
        raw = _ensure_v2_unlocked()
        servers = [s for s in raw["servers"] if isinstance(s, dict)]
        if len(servers) <= 1: return False, "last"
        if not any(s.get("id") == sid for s in servers): return False, "missing"
        raw["servers"] = [s for s in servers if s.get("id") != sid]
        if raw.get("currentServerId") == sid:
            raw["currentServerId"] = raw["servers"][0]["id"]
        _write_raw(raw)
        return True, raw["currentServerId"]

def apply_current_server(clear_drafts=True):
    """reconfigure adapter / cfg / scene / drafts / sent / templates from the current server bucket.
    clear_drafts=True also clears ALL in-memory orders (draft + sent) then reloads
    both buckets for the current server — required for per-server isolation.
    Always clears in-memory scene/geom/stations cache first, then restores only this
    server's scene_cache bucket (empty for a new server → zero leftover LM/point cloud)."""
    st = load_settings()
    set_adapter(st.get("adapter") or "rds")
    set_base(st.get("base") or "")
    if st.get("pollSec"): S["cfg"]["pollSec"] = st["pollSec"]
    f0 = st.get("fields") if isinstance(st.get("fields"), dict) else {}
    S["cfg"]["blockByBlock"] = bool(f0.get("bbb"))
    try: S["cfg"]["incPollSec"] = float(f0.get("bbb_poll") or 1)
    except (TypeError, ValueError): S["cfg"]["incPollSec"] = 1.0
    with lock:
        if clear_drafts:
            S["orders"].clear()
        # wipe live scene so a previous server's LM/PC cannot linger
        S["geom"] = None; S["groups"] = []; S["robot_group"] = {}; S["prepoints"] = {}
        S["robots"].clear(); S["opos"].clear(); S["robots_raw"] = None
        S.pop("st_cache", None); S.pop("precands", None)
        SCENE_JOB.clear()
    bind_template_store(st.get("currentServerId") or st.get("id"))
    restore_scene_cache()  # no-op / empty when this server has no cache
    if clear_drafts:
        load_drafts()
        load_sent()
    return st

def select_server(sid, force=False):
    """switch active server: persist drafts+sent under old id, clear memory, load new buckets"""
    with lock:
        raw = _ensure_v2_unlocked()
        if not any(s.get("id") == sid for s in raw["servers"]):
            return False, "missing"
        old = raw.get("currentServerId")
        if old == sid and not force:
            return True, sid
        if old and old != sid:
            try: _save_drafts_for(old)
            except Exception: pass
            try: _save_sent_for(old)
            except Exception: pass
        raw["currentServerId"] = sid
        _write_raw(raw)
    apply_current_server(clear_drafts=True)
    return True, sid

def migrate_servers():
    """one-shot: flat settings.json -> servers list. Backup as settings.pre_server.json (copy). Idempotent.
    Always runs drafts/scene/sent nesting afterward so already-v2 installs still get sent_orders nested."""
    notes = []
    with lock:
        raw = _read_raw()
        if not raw:
            srv = default_server()
            _write_raw({"version": 2, "lang": "zh", "currentServerId": srv["id"], "servers": [srv]})
            notes.append("created empty v2 settings with default server")
        elif _is_v2(raw) and raw.get("version") == 2:
            raw = _ensure_v2_unlocked(raw)
            _write_raw(raw)
        else:
            # backup before rewrite
            bak = os.path.join(P["data"], "settings.pre_server.json")
            if os.path.exists(P["settings"]) and not os.path.exists(bak):
                shutil.copy2(P["settings"], bak)
                notes.append("backup " + os.path.basename(bak))
            lang = raw.get("lang") or "zh"
            servers = []
            # primary entry from flat fields
            base = normalize_base(raw.get("base") or "")
            adapter = raw.get("adapter") or "rds"
            m4 = raw.get("m4") if isinstance(raw.get("m4"), dict) else {}
            profs = m4.get("profiles") if isinstance(m4.get("profiles"), dict) else {}
            active_prof = m4.get("active") or (next(iter(profs)) if profs else None)
            if adapter == "m4" and active_prof and isinstance(profs.get(active_prof), dict):
                pb = normalize_base(profs[active_prof].get("base") or "") or base
                base = pb or base
            if not base: base = DEFAULT_BASE
            label = _host_label(base) or "默认"
            primary = default_server(base, name=label, adapter=adapter)
            for k in SERVER_KEYS:
                if k in ("name", "base", "adapter", "m4"): continue
                if k in raw: primary[k] = copy.deepcopy(raw[k])
            if isinstance(raw.get("m4"), dict):
                primary["m4"] = copy.deepcopy(raw["m4"])
            elif not primary.get("m4"):
                primary["m4"] = {"active": "default", "profiles": {}}
            servers.append(primary)
            # extra M4 profiles (other than the one folded into primary) become their own servers
            for pname, p in profs.items():
                if not isinstance(p, dict): continue
                if adapter == "m4" and pname == active_prof: continue
                pb = normalize_base(p.get("base") or "") or DEFAULT_BASE
                extra = default_server(pb, name=str(pname), adapter="m4")
                extra["m4"] = {"active": pname, "profiles": {pname: copy.deepcopy(p)}}
                servers.append(extra)
                notes.append("m4 profile %r -> server" % pname)
            new = {"version": 2, "lang": lang, "currentServerId": primary["id"], "servers": servers}
            _write_raw(new)
            notes.append("migrated flat settings -> %d server(s)" % len(servers))
    # migrate scene_cache + drafts + sent_orders nesting (best-effort, after unlock)
    try: _migrate_scene_cache_nesting()
    except Exception as e: notes.append("scene_cache nest: %s" % e)
    try: _migrate_drafts_nesting()
    except Exception as e: notes.append("drafts nest: %s" % e)
    try: _migrate_sent_nesting()
    except Exception as e: notes.append("sent nest: %s" % e)
    return notes

VS_ROLES = ["pre", "s", "script", "e", "lift"]

def migrate_vs_settings():
    """very old: global vs_on/vs_head/vs_tail + vsBlocks -> vsPerBlock (only once)"""
    st = load_settings()
    if not st or isinstance(st.get("vsPerBlock"), dict) or not isinstance(st.get("fields"), dict): return False
    f = st.get("fields") or {}
    def num(v, d=1.539):
        try: return float(v)
        except Exception: return d
    on = f.get("vs_on")
    if on is None and str(f.get("vs") or "").strip():
        try:
            v = json.loads(f["vs"]); on = isinstance(v, dict); f = dict(f, vs_head=v.get("head", 1.539), vs_tail=v.get("tail", 1.539))
        except Exception: on = False
    vsb = st.get("vsBlocks") if isinstance(st.get("vsBlocks"), list) else ["e", "lift"]
    h, t = num(f.get("vs_head")), num(f.get("vs_tail"))
    save_settings({"vsPerBlock": {r: {"on": bool(on) and r in vsb, "head": h, "tail": t} for r in VS_ROLES}})
    return True

def templates_dir(sid=None):
    """per-server template folder: <data>/templates/<serverId>/"""
    sid = sid or _current_server_id() or "default"
    # sanitize path segment (ids are srv_ + hex; still guard)
    sid = "".join(c for c in str(sid) if c.isalnum() or c in "-_") or "default"
    return os.path.join(P.get("templates") or os.path.join(P["data"], "templates"), sid)

def bind_template_store(sid=None):
    """point S['store'] at templates/<serverId>/ (creates the dir)."""
    d = templates_dir(sid)
    os.makedirs(d, exist_ok=True)
    S["store"] = T.Store(d)
    return S["store"]

def migrate_templates_nesting():
    """Move shared templates/*.json into templates/<currentServerId>/. Idempotent.
    Existing shared library becomes the original/current server's bucket so nothing is lost.
    New servers get their own folder (seeded with builtin default in add_server)."""
    notes = []
    root = P.get("templates") or os.path.join(P["data"], "templates")
    os.makedirs(root, exist_ok=True)
    sid = _current_server_id() or "default"
    flat = [f for f in os.listdir(root)
            if f.endswith(".json") and os.path.isfile(os.path.join(root, f))]
    if flat:
        dest = templates_dir(sid)
        os.makedirs(dest, exist_ok=True)
        bak = os.path.join(P["data"], "templates.pre_server")
        if not os.path.exists(bak):
            try:
                os.makedirs(bak, exist_ok=True)
                for f in flat:
                    shutil.copy2(os.path.join(root, f), os.path.join(bak, f))
                notes.append("backup templates.pre_server/")
            except Exception:
                pass
        for f in flat:
            src = os.path.join(root, f)
            dst = os.path.join(dest, f)
            if os.path.exists(dst):
                try: os.remove(src)
                except Exception: pass
            else:
                shutil.move(src, dst)
        notes.append("migrated %d template(s) -> templates/%s/" % (len(flat), sid))
    bind_template_store(sid)
    return notes

def _templates_tree_has_json():
    root = P.get("templates") or os.path.join(P["data"], "templates")
    if not os.path.isdir(root): return False
    for dirpath, _, filenames in os.walk(root):
        if any(f.endswith(".json") for f in filenames):
            return True
    return False

def migrate_templates():
    """Nest shared templates under current server; seed builtin default only on a truly empty
    first install (no template json anywhere). Never recreate default when other templates
    exist; never seed into a new empty server that sits beside an existing bucket."""
    st = load_settings(); notes = []
    notes.extend(migrate_templates_nesting())
    store = S["store"]
    names = store.names()
    if not names and not _templates_tree_has_json():
        t = T.from_legacy_settings(st) if st else None
        store.put(t or T.builtin_default()); notes.append("templates/default.json created" + (" from legacy settings" if t else ""))
        names = store.names()
    part = {}
    if not isinstance(st.get("pools"), dict):
        part["pools"] = normalize_pools({"start": list(st.get("starts") or []), "end": list(st.get("ends") or [])})
        notes.append("pools migrated from starts/ends")
    notes.extend(migrate_pool_entries())
    act = st.get("activeTemplate")
    if names and (not act or act not in names):
        part["activeTemplate"] = names[0]
    elif not names and act:
        part["activeTemplate"] = ""
    if part:
        if os.path.exists(P["settings"]) and not os.path.exists(P["settings"] + ".bak-v1"):
            shutil.copy2(P["settings"], P["settings"] + ".bak-v1")
        save_settings(part)
    return notes

# ---------------------------------------------------------------- log
def log(kind, **kw):
    kw.update(ts=time.time(), t=datetime.datetime.now().isoformat(timespec="milliseconds"), kind=kind)
    with lock, open(P["log"], "a", encoding="utf-8") as f: f.write(json.dumps(kw, ensure_ascii=False) + "\n")

def set_base(url):
    """Set adapter base URL. None = leave unchanged; empty string clears (blank server)."""
    if url is None: return
    if getattr(AD(), "base_from_settings", True):
        AD().base = url or ""

# ---------------------------------------------------------------- adapter selection / M4 connection profiles
# settings.json (gitignored): "adapter": "rds"|"m4", "m4": {"active": name, "profiles": {name: {base, sceneId, auth,
# appId, appKey, username, password, opMode}}}. Secrets are masked in every API response and never logged.
M4_FIELDS = ("base", "sceneId", "sceneName", "auth", "appId", "appKey", "username", "password", "opMode")
def m4_settings():
    m = load_settings().get("m4")
    m = m if isinstance(m, dict) else {}
    profs = m.get("profiles") if isinstance(m.get("profiles"), dict) else {}
    return {"active": m.get("active") or (next(iter(profs)) if profs else "default"), "profiles": profs}

def m4_profile(name=None):
    m = m4_settings(); return dict(m["profiles"].get(name or m["active"]) or {})

def m4_masked():
    from .adapters.m4 import mask
    m = m4_settings(); return {"active": m["active"], "profiles": {k: mask(v) for k, v in m["profiles"].items()}}

def m4_save(name, prof, activate=True, delete=False):
    """store one profile; a masked secret ('******') keeps the stored value"""
    from .adapters.m4 import MASK, SECRET_KEYS
    name = (name or "default").strip() or "default"
    with lock:
        m = m4_settings(); profs = dict(m["profiles"])
        if delete:
            profs.pop(name, None); act = m["active"] if m["active"] != name else (next(iter(profs)) if profs else "default")
        else:
            old = profs.get(name) or {}; new = {}
            for k in M4_FIELDS:
                v = (prof or {}).get(k, old.get(k, ""))
                if k in SECRET_KEYS and v == MASK: v = old.get(k, "")
                new[k] = v.strip() if isinstance(v, str) else v
            profs[name] = new; act = name if activate else m["active"]
        part = {"m4": {"active": act, "profiles": profs}}
        # keep server.base in sync so the sidebar shows the M4 URL (saveCfg clears settings.base for M4)
        if not delete:
            pb = normalize_base((profs.get(act) or {}).get("base") or "")
            if pb: part["base"] = pb
        save_settings(part)
    return act

def set_adapter(name):
    """switch the active dispatcher adapter (rds default); M4 takes base/auth/sceneId from the active profile"""
    name = name or "rds"
    opts = m4_profile() if name == "m4" else None
    cur = AD()
    if cur is not None and cur.name == name:
        if opts is not None: cur.configure(opts)
        return cur
    rds_base = load_settings().get("base") or (cur.base if cur is not None and getattr(cur, "base_from_settings", True) else "http://127.0.0.1:8088")
    S["adapter"] = get_adapter(name, (opts or {}).get("base") or rds_base, log, opts)
    S["geom"] = None; S["groups"] = []; S["robot_group"] = {}; S["prepoints"] = {}; S.pop("st_cache", None)
    return S["adapter"]

def masked_settings():
    st = load_settings()
    if isinstance(st.get("m4"), dict): st["m4"] = m4_masked()
    return st

# ---------------------------------------------------------------- scene
def set_groups(js):
    gs = AD().parse_groups(js)
    if gs:
        with lock: S["groups"] = gs; S["robot_group"] = {rid: g["name"] for g in gs for rid in g["robots"]}

def load_scene_stations():
    st, js, txt = AD().scene()
    if js is None: return None, "/scene %s %s" % (st, txt[:200])
    try: set_groups(js); stations = AD().parse_stations(js)
    except Exception as e: return None, "/scene parse error: %s" % e
    S["st_cache"] = (time.time(), stations)
    with lock: S["prepoints"] = {p["name"]: p["pre"] for p in stations if p.get("pre")}; S["precands"] = _precands(stations)
    return stations, ""

def ensure_prepoints():
    if not S["prepoints"]:
        st, err = load_scene_stations()
        return err
    return ""

def _sha1(b): import hashlib; return hashlib.sha1(b).hexdigest()

def load_smap(path, progress=None, need_curves=True):
    """(curves, points, cell) from a .smap. The point cloud cache is keyed by the file's content hash, so an identical
    map is never parsed twice. need_curves=False (routes already known from /scene) skips route tessellation."""
    prog = progress or (lambda *a, **k: None)
    with open(path, "rb") as f: raw = f.read()
    h = _sha1(raw)
    try:
        with open(P["smap_cache"], encoding="utf-8") as f: c = json.load(f)
        if c.get("sha1") == h and (c.get("curves") is not None or not need_curves):
            prog("mapcache"); return c.get("curves") or [], [tuple(p) for p in c["points"]], c.get("cell")
    except Exception: pass
    prog("mapparse")
    curves, pts = [], []
    for js in AD().decode_map(raw):
        c, p = AD().extract_geom(js, points_only=not need_curves); curves += c; pts += p
    if not curves and not pts: raise ValueError("no 2D map JSON in file")
    prog("downsample", len(pts))
    pts, cell = rds_scene.downsample(pts)
    pts = [(round(x, 3), round(y, 3)) for x, y in pts]
    try:
        with open(P["smap_cache"], "w", encoding="utf-8") as f:
            json.dump({"sha1": h, "path": os.path.abspath(path), "curves": curves if need_curves else None, "points": pts, "cell": cell}, f)
    except Exception as e: log("smap_cache_err", err=str(e))
    return curves, pts, cell

def _precands(stations):
    out = {}
    for q in stations:
        info = q.get("preInfo")
        if not info and q.get("preCands"): info = [{"name": c, "dir": None, "dist": None, "lm": None} for c in q["preCands"]]  # old cache
        if info: out[q["name"]] = info
    return out

def _apply_geom(g):
    """make a successfully loaded scene the current one (memory)"""
    with lock:
        S["geom"] = g; st = g.get("stations") or []
        if st: S["prepoints"] = {q["name"]: q["pre"] for q in st if q.get("pre")}; S["precands"] = _precands(st); S["st_cache"] = (g.get("loadedAt") or time.time(), st)
        gs = g.get("groups") or []
        if gs: S["groups"] = gs; S["robot_group"] = {rid: x["name"] for x in gs for rid in x["robots"]}

def _current_server_id():
    st = load_settings()
    return st.get("currentServerId") or st.get("id") or "default"

def _read_scene_cache_file():
    try:
        with open(P["scene_cache"], encoding="utf-8") as f: return json.load(f)
    except Exception: return None

def _migrate_scene_cache_nesting():
    """flat scene_cache.json -> {byServer: {id: geom}}. Keeps original keys under current server."""
    g = _read_scene_cache_file()
    if not isinstance(g, dict): return
    if isinstance(g.get("byServer"), dict): return
    if not (g.get("ok") and g.get("stations")): return
    sid = _current_server_id()
    nested = {"byServer": {sid: g}}
    tmp = P["scene_cache"] + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(nested, f, ensure_ascii=False)
    os.replace(tmp, P["scene_cache"])

def save_scene_cache(g):
    try:
        sid = _current_server_id()
        cur = _read_scene_cache_file()
        if isinstance(cur, dict) and isinstance(cur.get("byServer"), dict):
            store = dict(cur); store["byServer"] = dict(cur["byServer"]); store["byServer"][sid] = g
        elif isinstance(cur, dict) and cur.get("ok") and cur.get("stations"):
            # legacy flat mid-flight: nest both
            old_sid = sid
            store = {"byServer": {old_sid: cur, sid: g}}
        else:
            store = {"byServer": {sid: g}}
        tmp = P["scene_cache"] + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(store, f, ensure_ascii=False)
        os.replace(tmp, P["scene_cache"])
    except Exception as e: log("scene_cache_save_fail", err=str(e))

def backfill_dirs(g, path=None):
    """old scene cache without station headings: fill 'dir' from the local .smap (no RDS download). Returns count."""
    try:
        st0 = load_settings(); cands = [path] if path else [st0.get("smapPath"), st0.get("smapAuto")]
        fp = next((c for c in cands if c and os.path.isfile(c)), None)
        if not fp: log("dir_backfill", n=0, note="no local smap"); return 0
        with open(fp, "rb") as f: raw = f.read()
        dm = {}
        for js in AD().decode_map(raw): dm.update({k: v for k, v in rds_scene.point_dirs(js).items() if k not in dm})
        n = 0
        with lock:
            for q in g.get("stations") or []:
                v = dm.get(q.get("name"))
                if v is None or isinstance(q.get("dir"), (int, float)): continue
                q["dir"] = round(v[0], 6); q["dirDeg"] = round(math.degrees(v[0]), 1); q["dirField"] = "dir (smap)"
                if v[1]: q["ignoreDir"] = True
                n += 1
            if n: g["dirSrc"] = "smap: " + os.path.basename(fp)
        if n and not g.get("sceneErr"): save_scene_cache({k: v for k, v in g.items() if k != "fromCache"})
        log("dir_backfill", n=n, smap=fp); return n
    except Exception as e:
        log("dir_backfill_fail", err=str(e)); return 0

def restore_scene_cache():
    """last successful scene load for the current server survives page reloads and server restarts"""
    try:
        blob = _read_scene_cache_file()
        if not isinstance(blob, dict): return False
        if isinstance(blob.get("byServer"), dict):
            g = blob["byServer"].get(_current_server_id())
        else:
            g = blob  # legacy flat
        if isinstance(g, dict) and g.get("ok") and g.get("stations"):
            g = dict(g); g["fromCache"] = True; _apply_geom(g)
            if not any(isinstance(q.get("dir"), (int, float)) for q in g["stations"]):
                threading.Thread(target=backfill_dirs, args=(g,), daemon=True).start()
            return True
    except FileNotFoundError: pass
    except Exception as e: log("scene_cache_load_fail", err=str(e))
    return False

SCENE_JOB = {}  # the one scene-load job: {id, stage, done, total, t0, t, finished, result}

def start_scene_job(refresh=False):
    """run build_geom in the background; concurrent callers share the running job"""
    with lock:
        j = SCENE_JOB
        if j and not j.get("finished"): return j["id"]
        jid = uuid.uuid4().hex[:12]
        SCENE_JOB.clear(); SCENE_JOB.update(id=jid, stage="request", done=None, total=None, t0=time.time(), t=time.time(), finished=False, result=None)
    def prog(stage, done=None, total=None):
        if SCENE_JOB.get("id") != jid: return
        SCENE_JOB.update(stage=stage, done=done, total=total, t=time.time())
    def run():
        try: g = build_geom(refresh=refresh, progress=prog)
        except Exception as e: g = {"ok": False, "err": str(e)}
        SCENE_JOB.update(finished=True, result=g, stage="done" if g.get("ok") and not g.get("sceneErr") else "failed", t=time.time())
    threading.Thread(target=run, daemon=True).start()
    return jid

def scene_job_status(jid):
    j = dict(SCENE_JOB)
    if not j or j.get("id") != jid: return {"ok": False, "err": "unknown job"}
    j["ok"] = True; j["elapsed"] = round(time.time() - j["t0"], 1)
    if not j["finished"]: j.pop("result", None)
    return j

def build_geom(refresh=False, progress=None):
    prog = progress or (lambda *a, **k: None)
    notes = []; curves, pts, cell = [], [], None; psrc = ""; csrc = ""; stations = []
    st, js, txt = AD().scene(progress=prog)
    scene_err = ""
    if js is not None:
      try:
        prog("parse")
        set_groups(js)
        curves, p0 = AD().extract_geom(js); stations = AD().parse_stations(js)
        csrc = "/scene" if curves else ""
        prog("pointcloud")
        if p0: prog("downsample", len(p0)); pts, cell = rds_scene.downsample(p0); psrc = "/scene normalPosList"
        else: notes.append("/scene: no point cloud (normalPosList)")
      except Exception as e:
        scene_err = "/scene parse error: %s" % e; js = None; curves, stations = [], []; notes.append(scene_err)
    else: scene_err = "/scene %s %s" % (st, txt[:200]); notes.append("/scene failed: %s %s" % (st, txt[:120]))
    smap = load_settings().get("smapPath")
    if not pts and smap:
        if os.path.isfile(smap):
            try:
                c2, pts, cell = load_smap(smap, prog, need_curves=not curves); psrc = "smap: " + smap
                if not curves and c2: curves = c2; csrc = "smap: " + smap
            except Exception as e: notes.append("smap parse failed %s: %s" % (smap, e))
        else: notes.append("smapPath not found: " + smap)
    auto = load_settings().get("smapAuto")
    if not pts and auto and os.path.isfile(auto) and not refresh:
        try:
            c2, pts, cell = load_smap(auto, prog, need_curves=not curves); psrc = "/downloadScene (cache " + os.path.basename(auto) + ")"
            if not curves and c2: curves = c2; csrc = psrc
        except Exception as e: notes.append("cached map parse failed: %s" % e)
    if not pts and js is not None:
        code, raw = AD().download_maps(progress=prog)
        if code == 200 and raw[:2] == b"PK":
            try:
                prog("mapparse")
                zf = zipfile.ZipFile(io.BytesIO(raw)); seen = {}
                for nm in zf.namelist():
                    if nm.lower().endswith(".smap") and os.path.basename(nm) not in seen: seen[os.path.basename(nm)] = nm
                if seen:
                    os.makedirs(P["maps"], exist_ok=True)
                    datas = {b2: zf.read(nm) for b2, nm in seen.items()}
                    h = _sha1(b"".join(k.encode() + b"\0" + _sha1(v).encode() for k, v in sorted(datas.items())))
                    dst = os.path.join(P["maps"], "rds_" + next(iter(seen))) if len(seen) == 1 else os.path.join(P["maps"], "rds_scene_maps.smap")
                    st0 = load_settings()
                    if st0.get("smapAuto") == dst and st0.get("smapAutoHash") == h and os.path.isfile(dst):
                        notes.append("/downloadScene: map unchanged, reused")  # same content: keep file -> point cloud cache stays valid
                    else:
                        if len(seen) == 1:
                            with open(dst, "wb") as f: f.write(next(iter(datas.values())))
                        else:
                            with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as out:
                                for b2, d in datas.items(): out.writestr(b2, d)
                        save_settings({"smapAuto": dst, "smapAutoHash": h})
                    c2, pts, cell = load_smap(dst, prog, need_curves=not curves); psrc = "/downloadScene (" + ", ".join(seen) + ")"
                    if not curves and c2: curves = c2; csrc = psrc
                else: notes.append("/downloadScene: zip without .smap")
            except Exception as e: notes.append("/downloadScene parse failed: %s" % e)
        else: notes.append("/downloadScene unavailable (HTTP %s)" % code)
    if not pts: notes.append("no point cloud in scene/map download (normalPosList); check dispatcher scene or /downloadScene")
    g = {"ok": True, "curves": curves, "points": [c for p in pts for c in p], "npoints": len(pts), "cell": cell,
         "bounds": rds_scene.geom_bounds(curves, pts, stations), "stations": stations, "pointSrc": psrc, "curveSrc": csrc, "notes": notes, "sceneErr": scene_err}
    if not scene_err:
        prog("cache")
        g["loadedAt"] = time.time(); g["groups"] = S.get("groups") or []
        _apply_geom(g); save_scene_cache(g)
    elif not S.get("geom"): S["geom"] = g   # keep the last good scene on failure
    log("geom", npoints=len(pts), ncurves=len(curves), pointSrc=psrc, curveSrc=csrc, notes=notes)
    return g

def load_groups_bg():
    st, js, _ = AD().scene()
    if js is not None: set_groups(js)

def order_state(oid):
    """current order state with light cache (active 5 s, terminal 10 min)"""
    now = time.time(); c = S["odcache"].get(oid)
    if c and now - c[1] < (600 if c[0] in TERMINAL() else 5): return c[0]
    r = AD().order_status(oid, timeout=5)
    state = (r or {}).get("state") or ""
    S["odcache"][oid] = (state or "?", now)
    if len(S["odcache"]) > 500:
        for k in sorted(S["odcache"], key=lambda k: S["odcache"][k][1])[:200]: S["odcache"].pop(k, None)
    return state or "?"

PRE_LINE_RE = __import__("re").compile(r"^\s*([^\s=:|,，]+)\s*(?:[=:]\s*|[\s,，]+)(.*?)\s*$")
PRE_VAL_RE = __import__("re").compile(r"^[^\s=:|,，]+$")

def parse_pre_text(text):
    """manual pre-point map text -> ({station: [pre, ...]}, [errors]).
    One station per line: AP1=LM1 | AP1=LM1|LM2 (also 'AP1:LM1', legacy 'AP1 LM1' / 'AP1,LM1'). '#' starts a comment."""
    out, errs = {}, []
    for i, raw in enumerate((text or "").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line: continue
        m = PRE_LINE_RE.match(line)
        vals = [v.strip() for v in m.group(2).split("|")] if m else []
        if not m or not vals or any(not PRE_VAL_RE.match(v) for v in vals):
            errs.append(msg("srv.preLineBad", n=i, line=raw.strip())); continue
        st = m.group(1)
        if st in out: errs.append(msg("srv.preLineDup", n=i, st=st)); continue
        out[st] = list(dict.fromkeys(vals))
    return out, errs

def _ov_list(cfg, name):
    v = (cfg.get("preOverrides") or {}).get(name)
    if not v: return []
    if isinstance(v, str): return [x.strip() for x in v.split("|") if x.strip()]
    return [str(x) for x in v if x]

def pre_point(name, cfg):
    ov = _ov_list(cfg, name)
    if ov: return ov[0]
    return S["prepoints"].get(name, "")

def pre_cands(name, cfg):
    """candidates for the pre-point selectors: manual values (enriched with scene info) or the scene list"""
    scene = S.get("precands", {}).get(name) or ([{"name": S["prepoints"][name], "dir": None, "dist": None, "lm": None}] if S["prepoints"].get(name) else [])
    ov = _ov_list(cfg, name)
    if not ov: return scene
    by = {c["name"]: c for c in scene}
    return [dict(by.get(v) or {"name": v, "dir": None, "dist": None, "lm": None}, manual=True) for v in ov]

# ---------------------------------------------------------------- templates / cfg
def resolve_template(b):
    """request -> template. Accepts {template: obj}, {templateName}, or the legacy flat form (startOp/...)."""
    if isinstance(b.get("template"), dict):
        t = json.loads(json.dumps(b["template"])); errs = T.validate(t)
        if errs: raise ValueError("; ".join(errs))
        return t
    if "startOp" in b or "scriptOn" in b: return T.from_legacy_cfg(b)
    name = b.get("templateName") or load_settings().get("activeTemplate") or "default"
    t = S["store"].get(name)
    if t is None: raise ValueError("template not found: " + name)
    return t

def normalize_pools(pools):
    """Canonical pool map. Strings stay strings; ``{station}`` without a bin becomes a string; ``{station, bin}`` is kept."""
    if not isinstance(pools, dict): return pools
    return {str(k): T.normalize_pool_list(v if isinstance(v, list) else []) for k, v in pools.items() if isinstance(k, str)}

def migrate_pool_entries():
    """Rewrite each server's pools into the canonical shape. Idempotent; no note when nothing changes."""
    notes = []
    with lock:
        raw = _read_raw()
        if not _is_v2(raw): return notes
        changed = False
        for s in raw.get("servers") or []:
            if not isinstance(s, dict) or not isinstance(s.get("pools"), dict): continue
            norm = normalize_pools(s["pools"])
            if norm != s["pools"]:
                s["pools"] = norm
                changed = True
        if changed:
            _write_raw(raw)
            notes.append("pools normalized (station/bin entries)")
    return notes

def cfg_pools(b, t):
    """{pool: [station | {station, bin?}]} for the template's pools (deduplicated). Legacy startPool/endPool accepted."""
    pools = dict(b.get("pools") or {})
    if b.get("startPool") is not None: pools["start"] = b["startPool"]
    if b.get("endPool") is not None: pools["end"] = b["endPool"]
    return {r: T.normalize_pool_list(pools.get(r) or []) for r in T.pool_roles(t)}

def prepare_cfg(b):
    """validate pools + pre-points. returns (cfg, template, pools, warn, err)"""
    set_base(b.get("base"))
    if "preOverridesText" in b:
        ov, perr = parse_pre_text(b.get("preOverridesText"))
        if perr: return b, None, {}, "", "\n".join(perr)
        b["preOverrides"] = ov
    try: t = resolve_template(b)
    except ValueError as e: return b, None, {}, "", str(e)
    pools = cfg_pools(b, t); roles = T.pool_roles(t)
    if not roles: return b, t, pools, "", msg("srv.noPoolStep")
    empty = [r for r in roles if not pools[r]]
    if empty: return b, t, pools, "", msg("srv.poolEmpty", pools=", ".join(empty))
    if b.get("noSelf", True) and len(roles) > 1 and all(len(pools[r]) == 1 for r in roles) and len({T.entry_station(pools[r][0]) for r in roles}) < len(roles):
        return b, t, pools, "", msg("srv.sameOnly")
    warn = []
    need = T.needed_pre_roles(t)
    if need:
        err = ensure_prepoints()
        if err and not S["prepoints"] and not b.get("preOverrides"): return b, t, pools, "", msg("srv.sceneFail", err=err)
        for r in roles:
            if r not in need: continue
            miss_e = [x for x in pools[r] if not pre_point(T.entry_station(x), b)]
            if miss_e:
                miss = sorted({T.entry_label(x) for x in miss_e})
                gone = {T.entry_station(x) for x in miss_e}
                warn.append(msg("srv.noPre", pool=r, list=", ".join(miss))); log("no_prepoint", pool=r, stations=sorted(gone))
                pools[r] = [x for x in pools[r] if T.entry_station(x) not in gone]
                if not pools[r]: return b, t, pools, "", "\n".join(warn) + " " + msg("srv.poolNowEmpty", pool=r)
    return b, t, pools, "\n".join(warn), ""

def _use_bin_targets():
    """Bin names are M4 step locations only. RDS keeps sending the station."""
    return AD().name == "m4"

def station_bins(name):
    """Bin names bound to one station in the loaded scene, in list order. Empty when unknown or none.
    The current geom wins over an older station cache. This is not every bin on the map."""
    if not name: return []
    rows = []
    g = S.get("geom") or {}
    if isinstance(g, dict): rows.extend(g.get("stations") or [])
    cache = S.get("st_cache")
    if isinstance(cache, (list, tuple)) and len(cache) == 2 and isinstance(cache[1], list):
        rows.extend(cache[1])
    for q in rows:
        if not isinstance(q, dict) or q.get("name") != name: continue
        b = q.get("bins") or []
        if not isinstance(b, list): return []
        out, seen = [], set()
        for x in b:
            n = str(x or "").strip()
            if n and n not in seen: seen.add(n); out.append(n)
        return out
    return []

def make_draft(picks, t, cfg, oid=None):
    """neutral order -> adapter payload -> draft record (ValueError: missing pre-point or bin selector)"""
    order = T.build_order(t, picks, cfg, lambda n: pre_point(n, cfg), oid, cands_of=lambda n: pre_cands(n, cfg), bin_targets=_use_bin_targets(), bins_of=station_bins)
    body = AD().build_payload(order)
    roles = T.pool_roles(t)
    g = lambda x: "%g" % x if isinstance(x, (int, float)) else str(x)
    vsTag = ",".join("%s%s/%s" % (st["name"], g(st["variableShape"].get("head")), g(st["variableShape"].get("tail")))
                     for st in order["steps"] if isinstance(st.get("variableShape"), dict))
    first, last = (picks.get(roles[0], ""), picks.get(roles[-1], "")) if roles else ("", "")
    now = time.time(); dpre = pre_point(T.entry_station(last), cfg)
    stored = {}
    for r in roles:
        stored[r] = T.normalize_entry(picks.get(r, "")) or ""
    return {"id": body["id"], "pair": [T.entry_label(picks[r]) for r in roles], "picks": stored, "template": t.get("name"), "adapter": AD().name,
            "pre": dpre, "dropPre": dpre, "pickPre": pre_point(T.entry_station(first), cfg) if len(roles) > 1 else "", "preChosen": order.get("preChosen") or [], "binChosen": order.get("binChosen") or [],
            "vsTag": vsTag, "vehicle": body.get("vehicle", ""), "group": body.get("group", ""), "state": DRAFT,
            "sent": now, "changed": now, "created": now, "sig": "", "error": None, "body": body}

def preview(b):
    """sample order for the template editor: first station of each pool (or placeholders)"""
    t = resolve_template(b); roles = T.pool_roles(t); pools = cfg_pools(b, t)
    picks = {}
    seen = set()
    for i, r in enumerate(roles):
        cand = [x for x in pools.get(r, []) if T.entry_station(x) not in seen] or pools.get(r) or ["<%s>" % r]
        picks[r] = cand[0]
        seen.add(T.entry_station(picks[r]))
    def pre(n): return pre_point(n, b) or ("<pre:%s>" % n if b.get("placeholderPre", True) else "")
    if "preOverridesText" in b:
        ov, perr = parse_pre_text(b.get("preOverridesText"))
        if perr: raise ValueError("\n".join(perr))
        b["preOverrides"] = ov
    def cands(n):
        c = pre_cands(n, b)
        return c if c else None  # no scene yet -> placeholder via pre()
    order = T.build_order(t, picks, b, pre, "dl-preview", cands_of=cands, lenient=b.get("placeholderPre", True) and not S["prepoints"], bin_targets=_use_bin_targets(), bins_of=station_bins)
    return {"ok": True, "picks": picks, "order": order, "payload": AD().build_payload(order)}

# ---------------------------------------------------------------- persistence
def is_active(o): return o["state"] not in TERMINAL() and o["state"] != DRAFT and not o.get("error")
def count_active(): return sum(1 for o in S["orders"].values() if is_active(o))

def _upgrade_record(o):
    """old records (start/end only) -> picks/template/adapter"""
    if not isinstance(o.get("picks"), dict):
        pr = o.get("pair") if isinstance(o.get("pair"), list) else []
        o["picks"] = {"start": pr[0] if len(pr) > 0 else "?", "end": pr[1] if len(pr) > 1 else "?"}
    o.setdefault("template", "default"); o.setdefault("adapter", "rds")
    return o

def _read_drafts_file():
    try:
        with open(P["drafts"], encoding="utf-8-sig") as f: return json.load(f)
    except Exception: return None

def _migrate_drafts_nesting():
    """flat drafts.json list -> {byServer: {id: [...]}} under current server."""
    d = _read_drafts_file()
    if d is None: return
    if isinstance(d, dict) and isinstance(d.get("byServer"), dict): return
    if not isinstance(d, list): return
    sid = _current_server_id()
    nested = {"byServer": {sid: d}}
    tmp = P["drafts"] + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(nested, f, ensure_ascii=False)
    os.replace(tmp, P["drafts"])

def _save_drafts_for(sid):
    with lock:
        d = [o for o in S["orders"].values() if o["state"] == DRAFT]
    blob = _read_drafts_file()
    if isinstance(blob, dict) and isinstance(blob.get("byServer"), dict):
        store = dict(blob); store["byServer"] = dict(blob["byServer"]); store["byServer"][sid or "default"] = d
    elif isinstance(blob, list):
        store = {"byServer": {(sid or "default"): d}}
    else:
        store = {"byServer": {(sid or "default"): d}}
    tmp = P["drafts"] + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(store, f, ensure_ascii=False)
    os.replace(tmp, P["drafts"])

def save_drafts():
    _save_drafts_for(_current_server_id())

def _read_sent_file():
    try:
        with open(P["sent"], encoding="utf-8-sig") as f: return json.load(f)
    except Exception: return None

def _migrate_sent_nesting():
    """flat sent_orders.json list -> {byServer: {id: [...]}} under current server.
    Idempotent. Backs up the flat file as sent_orders.pre_server.json before rewrite."""
    d = _read_sent_file()
    if d is None: return
    if isinstance(d, dict) and isinstance(d.get("byServer"), dict): return
    if not isinstance(d, list): return
    sid = _current_server_id()
    bak = os.path.join(P["data"], "sent_orders.pre_server.json")
    if os.path.exists(P["sent"]) and not os.path.exists(bak):
        shutil.copy2(P["sent"], bak)
    nested = {"byServer": {sid: d}}
    tmp = P["sent"] + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(nested, f, ensure_ascii=False)
    os.replace(tmp, P["sent"])

_sent_sig = [None]
def _save_sent_for(sid):
    """Write only this server's non-draft orders into its byServer bucket (other buckets untouched)."""
    try:
        _migrate_sent_nesting()
        with lock: d = [o for o in S["orders"].values() if o["state"] != DRAFT]
        key = sid or "default"
        sig = key + "|" + json.dumps([(o["id"], o["state"], o.get("sig"), o.get("changed"), o.get("vehicle"), o.get("error"), o.get("started"), o.get("ended"), o.get("assigned"), o.get("batch"), o.get("inc")) for o in d], ensure_ascii=False)
        if sig == _sent_sig[0]: return
        blob = _read_sent_file()
        if isinstance(blob, dict) and isinstance(blob.get("byServer"), dict):
            store = dict(blob); store["byServer"] = dict(blob["byServer"]); store["byServer"][key] = d
        elif isinstance(blob, list):
            store = {"byServer": {key: d}}
        else:
            store = {"byServer": {key: d}}
        tmp = P["sent"] + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(store, f, ensure_ascii=False)
        os.replace(tmp, P["sent"]); _sent_sig[0] = sig
    except Exception as e: print("save_sent error:", e, flush=True)

def save_sent():
    _save_sent_for(_current_server_id())

def load_sent():
    try:
        blob = _read_sent_file()
        if blob is None: return 0
        if isinstance(blob, dict) and isinstance(blob.get("byServer"), dict):
            d = blob["byServer"].get(_current_server_id()) or []
        elif isinstance(blob, list):
            d = blob  # legacy flat until migrate_servers / first save
        else:
            d = []
    except Exception: return 0
    if not isinstance(d, list): d = []
    n = 0
    with lock:
        for o in d:
            if not isinstance(o, dict) or not o.get("id") or o.get("state") == DRAFT or o["id"] in S["orders"]: continue
            for k in ("age", "idle"): o.pop(k, None)
            if o.get("state") not in TERMINAL() and o.get("ended"):  # old versions treated FAILED as terminal
                for k in ("ended", "endedSrc", "_tfill"): o.pop(k, None)
                o["_reopened"] = True
            now = time.time()
            for k, v in (("pair", ["?", "?"]), ("vehicle", ""), ("sig", ""), ("error", None), ("sent", now), ("changed", now), ("pre", "")): o.setdefault(k, v)
            S["orders"][o["id"]] = _upgrade_record(o); n += 1
    inc_revive()
    try: assign_hist_batches()
    except Exception as e: print("assign_hist_batches error:", e, flush=True)
    return n

def load_drafts():
    try:
        blob = _read_drafts_file()
        if blob is None: return 0
        if isinstance(blob, dict) and isinstance(blob.get("byServer"), dict):
            d = blob["byServer"].get(_current_server_id()) or []
        elif isinstance(blob, list):
            d = blob
        else:
            d = []
        n = 0
        with lock:
            for o in d:
                if isinstance(o, dict) and o.get("id") and o.get("state") == DRAFT:
                    S["orders"][o["id"]] = _upgrade_record(o); n += 1
        return n
    except Exception: return 0

# ---------------------------------------------------------------- batches
def _max_batch_no():
    return max([o["batchMeta"].get("no", 0) for o in S["orders"].values() if isinstance(o.get("batchMeta"), dict)] + [0])

def new_batch(ids, interval=None, max_active=None, kind="send", group=""):
    with lock: no = _max_batch_no() + 1
    return {"id": "b%d-%s" % (no, uuid.uuid4().hex[:6]), "no": no, "name": "#%d" % no, "start": time.time(), "n": len(ids),
            "interval": interval, "maxActive": max_active, "group": group, "kind": kind}

def _log_send_batches():
    out = []
    try: files = sorted(f for f in os.listdir(P["logs"]) if f.endswith(".jsonl"))
    except Exception: return out
    for fn in files:
        try:
            with open(os.path.join(P["logs"], fn), encoding="utf-8", errors="replace") as f:
                for line in f:
                    if '"send_batch"' not in line: continue
                    try: e = json.loads(line)
                    except Exception: continue
                    if e.get("kind") == "send_batch" and isinstance(e.get("ids"), list):
                        out.append((e.get("ts") or 0, e["ids"], e.get("interval"), e.get("maxActive")))
        except Exception: pass
    return sorted(out, key=lambda x: x[0])

def assign_hist_batches():
    with lock: todo = {k: o for k, o in S["orders"].items() if o["state"] != DRAFT and not o.get("batch")}
    if not todo: return 0
    groups = []
    for ts_, ids, iv, ma in reversed(_log_send_batches()):
        g = [i for i in ids if i in todo]
        if g:
            groups.append((g, "log", iv, ma))
            for i in g: todo.pop(i)
    rest = sorted(todo.values(), key=lambda o: o.get("sent") or 0); cur = []; prev = None
    for o in rest:
        if prev and ((o.get("sent") or 0) - (prev.get("sent") or 0) > HIST_GAP_SEC or
                     abs((o.get("created") or o.get("sent") or 0) - (prev.get("created") or prev.get("sent") or 0)) > HIST_CREATED_SEC):
            groups.append(([x["id"] for x in cur], "gap", None, None)); cur = []
        cur.append(o); prev = o
    if cur: groups.append(([x["id"] for x in cur], "gap", None, None))
    with lock:
        first = lambda g: min((S["orders"][i].get("sent") or 0) for i in g[0])
        base = _max_batch_no()
        for k, g in enumerate(sorted(groups, key=first), 1):
            ids, src, iv, ma = g; no = base + k
            grp = sorted({(S["orders"][i].get("body") or {}).get("group", "") for i in ids} - {""})
            meta = {"id": "h%d-%s" % (no, uuid.uuid4().hex[:6]), "no": no, "name": "#%d" % no, "start": first(g), "n": len(ids),
                    "interval": iv, "maxActive": ma, "group": ",".join(grp), "kind": "hist", "src": src}
            for i in ids: S["orders"][i]["batch"] = meta["id"]; S["orders"][i]["batchMeta"] = dict(meta)
    log("assign_hist_batches", n=len(groups), src={s_: sum(1 for g in groups if g[1] == s_) for s_ in ("log", "gap")})
    return len(groups)

def backfill_times():
    with lock: ids = [k for k, o in S["orders"].items() if o["state"] in TERMINAL() and not o.get("error") and o["state"] != "SKIPPED"
                      and (not o.get("ended") or not o.get("started")) and not o.get("_tfill")]
    for oid in ids:
        js = AD().order_status(oid)
        if js is None: continue
        bst = js.get("blockStartTimes") or []
        started = min(bst) if bst else js.get("receiveTime") or js.get("createTime")
        ended = js.get("terminateTime") or js.get("finishTime")
        with lock:
            o = S["orders"].get(oid)
            if not o: continue
            o["_tfill"] = True
            if started and not o.get("started"): o["started"] = started; o["startedSrc"] = "rds"
            if ended and not o.get("ended"): o["ended"] = ended; o["endedSrc"] = "rds"
        log("backfill_times", id=oid, started=started, ended=ended)

# ---------------------------------------------------------------- generate / swap / send
def generate_drafts(cfg, t, pools, rng=None, id_factory=None):
    ensure_prepoints()
    roles = T.pool_roles(t)
    picker = T.make_picker(cfg.get("strategy") or "random", [(r, pools[r]) for r in roles], cfg.get("noSelf", True), cfg.get("noReuse", True), rng)
    n = cfg.get("count"); n = picker.default_count() if n in (None, "") else int(n or 0)
    made, skipped = [], []
    for _ in range(n):
        try: picks = picker.next()
        except ValueError as e: skipped.append({"pair": [], "err": str(e)}); break
        try: rec = make_draft(picks, t, cfg, id_factory() if id_factory else None)
        except ValueError as e: skipped.append({"pair": [T.entry_label(picks[r]) for r in roles], "err": str(e)}); continue
        with lock: S["orders"][rec["id"]] = rec
        made.append(rec["id"])
    save_drafts()
    first = roles[0] if roles else None
    no_pick = sorted({T.entry_station(s) for s in pools.get("start", []) if not pre_point(T.entry_station(s), cfg)}) if "start" in roles and "start" not in T.needed_pre_roles(t) else []
    log("generate", n=len(made), template=t.get("name"), strategy=cfg.get("strategy") or "random", ids=made, skipped=skipped, pools=pools,
        noSelf=cfg.get("noSelf"), noReuse=cfg.get("noReuse"))
    return {"n": len(made), "ids": made, "skipped": skipped, "noPickPre": no_pick}

def swap_drafts(ids, cfg, t):
    """swap the first and last pool picks of the selected drafts; rebuild (draft's own template, else t); keep id + group"""
    ensure_prepoints(); done, errs = [], []
    for oid in ids:
        with lock:
            o = S["orders"].get(oid)
            if not o or o["state"] != DRAFT: errs.append({"id": oid, "err": msg("srv.notDraft")}); continue
            if S["running"] and oid in S.get("batch", ()): errs.append({"id": oid, "err": msg("srv.inBatch")}); continue
            old = dict(_upgrade_record(o)["picks"])
            # rebuild with the draft's own template (current saved version); fall back to the given one
            tt = S["store"].get(o["template"]) if o.get("template") and o["template"] in S["store"].names() else t
            roles = T.pool_roles(tt)
            vals = [old.get(r, "") for r in roles]
            if len(vals) >= 2: vals[0], vals[-1] = vals[-1], vals[0]
            picks = dict(zip(roles, vals))
            ocfg = dict(cfg, group=(o.get("body") or {}).get("group", ""))
        try: rec = make_draft(picks, tt, ocfg, oid)
        except ValueError as e: errs.append({"id": oid, "pair": [T.entry_label(v) for v in vals], "err": str(e)}); continue
        with lock:
            cur = S["orders"].get(oid)
            if not cur or cur["state"] != DRAFT: errs.append({"id": oid, "err": msg("srv.changed")}); continue
            rec["created"] = cur.get("created", rec["created"]); rec["swapped"] = cur.get("swapped", 0) + 1
            S["orders"][oid] = rec
        done.append({"id": oid, "pair": [T.entry_label(v) for v in vals]})
    save_drafts(); log("swap_drafts", done=done, errors=errs)
    return {"n": len(done), "done": done, "errors": errs}

# ---------------------------------------------------------------- block-by-block ("逐块下发") dispatch
# RDS doc: order FAILED/STOPPED/Error; block FAILED/STOPPED/Error. Block MANUAL_FINISHED (手动完成动作块) counts as done.
# Rule: appending stops for good ONLY on a terminal ORDER state (FINISHED / STOPPED, plus cancel/withdraw variants;
# a user cancel in the tool terminates the order in RDS -> STOPPED). Everything else - order FAILED/Error/SUSPENDED/
# WAITING/unknown, bad blocks, orderDetails errors/timeouts/"not found", addBlocks errors - only pauses (warning) and
# keeps polling: RDS has been seen to report an order FAILED transiently and then recover.
INC_STOP = frozenset({"FINISHED", "STOPPED", "CANCELED", "CANCELLED", "TERMINATED", "WITHDRAWN", "SKIPPED"})
INC_BLOCK_BAD = frozenset({"FAILED", "STOPPED", "Error", "ERROR"})
INC_ORDER_BAD = frozenset({"FAILED", "Error", "ERROR"})  # pause only
INC_BLOCK_DONE = frozenset({"FINISHED", "MANUAL_FINISHED"})
INC_ERR_LIMIT = 5  # consecutive addBlocks/markComplete errors before a warning is shown (appending keeps retrying)

def _inc_revivable(inc):
    """stopped by an older version for a non-terminal reason (order FAILED/Error, missing, repeated addBlocks errors)"""
    if not isinstance(inc, dict) or inc.get("status") != "stopped" or inc.get("sent", 0) < 1: return False
    r = str(inc.get("reason") or "")
    if r.startswith("setOrder"): return False  # order never created in RDS
    if r.startswith("order "):
        return r[6:].split(" ")[0] not in INC_STOP  # FAILED / Error / missing ...
    return " failed " in r and " times" in r

def inc_revive():
    """re-open block-by-block orders wrongly stopped by older versions; returns revived ids"""
    out = []
    with lock:
        for k, o in S["orders"].items():
            inc = o.get("inc")
            if o.get("body") and _inc_revivable(inc):
                old = inc.get("reason"); inc.update(status="appending", reason="", errs=0, revived=time.time(), warn="revived (was stopped: %s)" % old)
                inc.pop("tEnd", None); o["changed"] = time.time(); out.append(k)
                log("inc_revived", id=k, was=old, sent=inc.get("sent"), total=inc.get("total"))
    return out

def inc_enabled(cfg=None):
    return bool((cfg if cfg is not None else S["cfg"]).get("blockByBlock")) and getattr(AD(), "supports_incremental", False)

def submit_record(rec, inc=False):
    """send a draft record. inc: open order with only the first block, the rest is appended by inc_once()."""
    body = rec["body"]; ad = AD()
    blocks = ad.payload_blocks(body) if inc else []
    if inc and len(blocks) > 1:
        ok, err = ad.submit(ad.incremental_payload(body, 1))
        rec["inc"] = {"total": len(blocks), "sent": 1, "status": "appending" if ok else "stopped", "reason": "" if ok else "setOrder: " + str(err),
                      "errs": 0, "t": time.time(), "steps": [{"t": time.time(), "act": "setOrder", "block": ad.block_id(blocks[0]), "ok": ok}]}
        log("inc_start", id=rec["id"], total=len(blocks), ok=ok, err=err)
        return ok, err
    return ad.submit(body)

def _inc_stop(o, reason, status="stopped"):
    o["inc"].update(status=status, reason=reason, tEnd=time.time()); o["changed"] = time.time()
    log("inc_" + status, id=o["id"], reason=reason, sent=o["inc"]["sent"], total=o["inc"]["total"])

def inc_pending():
    with lock: return [k for k, o in S["orders"].items() if isinstance(o.get("inc"), dict) and o["inc"].get("status") == "appending"]

def inc_once():
    """one pass over open block-by-block orders: append the next block once the previous one is FINISHED.
    Idempotent: blocks already present in the dispatcher (e.g. appended before a restart) are not sent again."""
    ad = AD(); changed = bool(inc_revive())
    for oid in inc_pending():
        with lock:
            o = S["orders"].get(oid)
            if not o or not o.get("body"): continue
            inc = o["inc"]; blocks = ad.payload_blocks(o["body"])
        try: js = ad.order_status(oid)
        except Exception as e: js = None; log("inc_error", id=oid, act="orderDetails", err=str(e))
        if js is None: continue  # dispatcher unreachable / timeout: pause, retry next tick
        with lock:
            if js.get("missing"):  # not found (maybe transient): pause and keep polling
                w = "order not found in dispatcher (%s), waiting" % js.get("msg", "")
                if inc.get("warn") != w: inc["warn"] = w; o["changed"] = time.time(); changed = True; log("inc_warn", id=oid, warn=w)
                continue
            ids = js.get("blockIds") or []; states = dict(zip(ids, js.get("blockStates") or []))
            ours = [ad.block_id(b) for b in blocks]
            have = sum(1 for b in ours if b in states)
            if have > inc["sent"]: inc["sent"] = have; log("inc_resync", id=oid, sent=have)  # appended before a restart
            ost = js.get("state")
            if ost in INC_STOP:
                _inc_stop(o, "order %s" % ost); changed = True; continue
            bad = [(b, states[b]) for b in ours[:inc["sent"]] if states.get(b) in INC_BLOCK_BAD]
            w = None
            if ost in INC_ORDER_BAD: w = "order %s, paused, waiting for recovery" % ost
            elif bad: w = "block %s %s (order %s), waiting for recovery" % (bad[0][0], bad[0][1], ost)
            if w:
                if inc.get("warn") != w: inc["warn"] = w; o["changed"] = time.time(); changed = True; log("inc_warn", id=oid, warn=w)
            elif inc.pop("warn", None) is not None:
                o["changed"] = time.time(); changed = True; log("inc_recovered", id=oid, order=ost)
            last = ours[inc["sent"] - 1]
            if inc["sent"] < inc["total"] and states.get(last) not in INC_BLOCK_DONE: continue
            nxt = blocks[inc["sent"]] if inc["sent"] < inc["total"] else None
        if nxt is not None:
            ok, err = ad.add_blocks(oid, [nxt], complete=False); act = "addBlocks"
        else:
            ok, err = ad.mark_complete(oid); act = "markComplete"
        with lock:
            inc["steps"].append({"t": time.time(), "act": act, "block": ad.block_id(nxt) if nxt else "", "ok": ok}); inc["steps"] = inc["steps"][-50:]
            o["changed"] = time.time(); changed = True
            if not ok:
                inc["errs"] = inc.get("errs", 0) + 1; inc["lastErr"] = "%s: %s" % (act, err)
                log("inc_error", id=oid, act=act, err=err, n=inc["errs"])
                if inc["errs"] >= INC_ERR_LIMIT: inc["warn"] = "%s failed %d times (retrying): %s" % (act, inc["errs"], err)
                continue
            if inc.get("errs"): inc.pop("warn", None)
            inc["errs"] = 0; inc.pop("lastErr", None)
            if nxt is not None:
                inc["sent"] += 1; log("inc_add", id=oid, block=ad.block_id(nxt), sent=inc["sent"], total=inc["total"])
        if nxt is not None and inc["sent"] == inc["total"]:  # last block appended -> close the order right away
            ok, err = ad.mark_complete(oid)
            with lock:
                inc["steps"].append({"t": time.time(), "act": "markComplete", "block": "", "ok": ok})
                if not ok: inc["errs"] = 1; inc["lastErr"] = "markComplete: %s" % err; log("inc_error", id=oid, act="markComplete", err=err, n=1); continue
            nxt = None
        if nxt is None:
            with lock: _inc_stop(o, "", status="done")
    if changed: save_sent()
    return changed

def inc_worker():
    while True:
        try: inc_once()
        except Exception as e: log("inc_error", err=str(e))
        try: d = float(S["cfg"].get("incPollSec") or 1)
        except (TypeError, ValueError): d = 1.0
        time.sleep(max(0.2, d))

def send_batch(ids, interval, max_active, meta=None, inc=False):
    done = 0
    try:
        for oid in ids:
            while S["running"] and max_active and count_active() >= max_active: time.sleep(0.5)
            if not S["running"]: break
            with lock:
                o = S["orders"].get(oid)
                if not o or o["state"] != DRAFT: continue
            ok, err = submit_record(o, inc)
            now = time.time()
            with lock:
                o.update(state="SENT" if ok else "SEND_FAIL", sent=now, changed=now, error=err)
                if meta: o["batch"] = meta["id"]; o["batchMeta"] = meta
                S["sent"] += 1; done += 1; S["msg"] = "%d/%d" % (done, len(ids))
            save_drafts()
            t_end = time.time() + interval
            while S["running"] and time.time() < t_end and oid != ids[-1]: time.sleep(0.1)
    finally:
        left = sum(1 for i in ids if i in S["orders"] and S["orders"][i]["state"] == DRAFT)
        S["running"] = False; S["msg"] = msg("srv.sendEnd", n=done) + (msg("srv.sendLeft", n=left) if left else "")
        log("send_batch_end", sent=done, left=left)

def dispatcher(t, pools):
    """auto mode (/api/start): generate + send continuously, keeping at most maxActive open"""
    cfg = S["cfg"]; roles = T.pool_roles(t)
    picker = T.make_picker(cfg.get("strategy") or "random", [(r, pools[r]) for r in roles], cfg.get("noSelf", True), cfg.get("noReuse", True))
    while S["running"] and S["sent"] < int(cfg["count"]):
        with lock: active = count_active()
        if active >= int(cfg.get("maxActive") or 1): time.sleep(0.5); continue
        picks = picker.next()
        try: rec = make_draft(picks, t, cfg)
        except ValueError as e:
            log("order_skip", picks=picks, err=str(e)); now = time.time(); sid = "skip-" + uuid.uuid4().hex[:8]
            with lock:
                S["orders"][sid] = {"id": sid, "pair": [T.entry_label(picks[r]) for r in roles],
                                   "picks": {r: (T.normalize_entry(picks[r]) or "") for r in roles},
                                   "vehicle": "", "state": "SKIPPED", "sent": now, "changed": now, "sig": "", "error": str(e), "body": None}
                S["sent"] += 1
            continue
        ok, err = submit_record(rec, inc_enabled(cfg)); now = time.time()
        rec.update(state="SENT" if ok else "SEND_FAIL", sent=now, changed=now, error=err, batch=(S.get("dbatch") or {}).get("id"), batchMeta=S.get("dbatch"))
        with lock: S["orders"][rec["id"]] = rec; S["sent"] += 1
        t_end = time.time() + float(cfg.get("interval") or 0)
        while S["running"] and time.time() < t_end: time.sleep(0.1)
    S["running"] = False; S["msg"] = msg("srv.autoEnd")

# ---------------------------------------------------------------- polling
MISS_LIMIT = 3  # consecutive 'order not found' answers before an order is treated as cancelled in RDS
def poll_once():
    TERM = TERMINAL()
    with lock: ids = [k for k, o in S["orders"].items() if is_active(o)]
    for oid in ids:
        js = AD().order_status(oid)
        if js is None: continue
        if js.get("missing"):
            with lock:
                o = S["orders"][oid]; tnow = time.time()
                o.setdefault("_missAt", tnow); o["_miss"] = o.get("_miss", 0) + 1
                if o["_miss"] >= MISS_LIMIT:  # gone from RDS (cancelled/withdrawn there): terminal, freeze duration
                    o.update(state="CANCELED", gone=True, goneMsg=js.get("msg", ""), changed=tnow)
                    o["sig"] = "CANCELED|%s|%s" % (o.get("vehicle", ""), o.get("blocks", ""))
                    o["ended"] = o.pop("_missAt"); o["endedSrc"] = "rds-missing"; o.pop("_miss", None); o.pop("_reopened", None)
                    log("order_change", id=oid, state="CANCELED", gone=True, msg=js.get("msg", ""))
            continue
        with lock:
            o = S["orders"][oid]; o.pop("_miss", None); o.pop("_missAt", None)
            new = {"state": js["state"] if js.get("state") is not None else o["state"], "vehicle": js.get("vehicle") or o["vehicle"]}
            bl = js.get("blockStates") or []
            bsig = ",".join(str(b) for b in bl)
            sig = "%s|%s|%s" % (new["state"], new["vehicle"], bsig)
            if sig != o["sig"]:
                o["changed"] = time.time(); log("order_change", id=oid, state=new["state"], vehicle=new["vehicle"], blocks=bsig)
            tnow = time.time()
            if js.get("vehicle") and not o.get("assigned"):
                if o.get("started"): o["assigned"] = o["started"]
                else: o["assigned"] = tnow; o["changed"] = tnow  # first assignment: idle counts from here
            o.update(new, sig=sig, blocks=bsig)
            if not o.get("started"):
                began = new["state"] == "RUNNING" or bool(js.get("vehicle")) or any(b not in (None, "", "CREATED") for b in bl)
                if began or new["state"] in TERM: o["started"] = tnow; o["startedSrc"] = "poll"
            if new["state"] in TERM and not o.get("ended"):
                rt = js.get("terminateTime") if o.get("_reopened") else None
                if rt and rt <= tnow: o["ended"] = rt; o["endedSrc"] = "rds"
                else: o["ended"] = tnow; o["endedSrc"] = "poll"
            elif new["state"] not in TERM and o.get("ended"):
                o.pop("ended", None); o.pop("endedSrc", None)
    rl = AD().robots()
    if rl is not None:
        now = time.time()
        if not S["groups"] and now - S["groups_try"] > 300:
            S["groups_try"] = now; threading.Thread(target=load_groups_bg, daemon=True).start()
        ost_map = {}
        for r in rl:
            if r.get("order"): ost_map[r["order"]] = r.get("orderState") or order_state(r["order"])
        with lock:
            S["robots_raw"] = True
            # replace (not merge): drop robots absent from the new adapter list
            prev_all = S["robots"]
            rebuilt = {}
            for r in rl:
                name = r["name"]; x, y = r.get("x"), r.get("y"); cur = r.get("order") or ""
                prev = prev_all.get(name)
                moved = prev is None or prev["x"] is None or x is None or abs((x or 0) - (prev["x"] or 0)) + abs((y or 0) - (prev["y"] or 0)) > 0.05
                ost = ost_map.get(cur, "") if cur else ""
                rebuilt[name] = {"name": name, "x": x, "y": y, "station": r.get("station", ""), "order": cur,
                    "orderState": ost, "orderActive": bool(cur) and ost not in TERM,
                    "group": S["robot_group"].get(name) or r.get("group") or "",
                    "dispatchable": r.get("dispatchable"), "connected": r.get("connected"), "blocked": r.get("blocked"),
                    "battery": r.get("battery"), "angle": r.get("angle"), "moved": now if moved else prev["moved"]}
            S["robots"] = rebuilt
            # vehicle position/heading change also counts as order change
            byveh = {r["name"]: r for r in S["robots"].values()}
            for oid, o in S["orders"].items():
                if not is_active(o) or not o.get("vehicle") or not o.get("assigned"): S["opos"].pop(oid, None); continue
                rb2 = byveh.get(o["vehicle"])
                if not rb2 or rb2.get("x") is None or rb2.get("y") is None: continue
                if rb2.get("order") and rb2["order"] != oid: S["opos"].pop(oid, None); continue
                cur = (rb2["x"], rb2["y"], rb2.get("angle"))
                last = S["opos"].get(oid)
                if last is None or last[3] != o["vehicle"]: S["opos"][oid] = cur + (o["vehicle"],); continue
                d = math.hypot(cur[0] - last[0], cur[1] - last[1]); da = 0.0
                if cur[2] is not None and last[2] is not None:
                    da = abs((math.degrees(cur[2] - last[2]) + 180) % 360 - 180)
                if d > MOVE_EPS_M or da > MOVE_EPS_DEG:
                    o["changed"] = now; S["opos"][oid] = cur + (o["vehicle"],)
                    if now - S["omovelog"].get(oid, 0) >= MOVE_LOG_SEC:
                        S["omovelog"][oid] = now; log("order_move", id=oid, vehicle=o["vehicle"], x=cur[0], y=cur[1], angle=cur[2])

def poller():
    while True:
        try: poll_once()
        except Exception as e: log("poller_error", err=str(e))
        if time.time() - S.get("bf_t", 0) > 60:
            S["bf_t"] = time.time()
            try: backfill_times()
            except Exception as e: log("backfill_error", err=str(e))
        save_sent()
        time.sleep(float(S["cfg"].get("pollSec") or 2))
