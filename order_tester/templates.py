# -*- coding: utf-8 -*-
"""Dispatcher-neutral order templates.

A template is an ordered list of steps. Every step has
  id            unique key inside the template (also used for variableShape roles / blockId suffix)
  name          optional display note/label (used in vsTag when set; empty allowed)
  enabled       bool
  location      one of
                  {"type": "pool",  "pool": "<pool name>"}       random/round-robin/... pick from a named pool
                  {"type": "pre",   "step": "<step id>"}          pre-point of another step's station
                                                                  (scene AP->LM derivation or the override map)
                    optional "select": nearest (default) | index | name | dir | random, "selArg": see PRE_SELECT
                  {"type": "fixed", "station": "<station name>"}
  operation     operation name ("none" = move only)
  opMode        "binTask" | "operation" (per-step; both M4 and RDS). binTask = action name only;
                operation = action name + args. Missing: adapters fall back (M4: profile opMode/binTask;
                RDS: operation). Legacy args.m4Mode is migrated into opMode on validate.
  args          dict; strings may contain variables (see substitute())
  vsOn / variableShape   optional {"head": float, "tail": float}
  keepFinalPathSpace     optional bool, M4 only (step field 保持末段空间资源不释放); RDS ignores it
  blockSuffix   optional legacy override for per-step id suffix (default "-<id>"); UI no longer edits this — id is the suffix source for new edits

Adapters (order_tester.adapters.*) turn the neutral order produced by build_order() into a
dispatcher payload (e.g. RDS setOrder JSON).
"""
import copy, fnmatch, itertools, json, os, random, re, uuid

DEFAULT_ARGS_START = {"disable_laser_id": 3, "end_height": 0.2, "rec_height": 0.09, "rec_target_obs": True,
                      "recfile": "plt/p0005.plt", "recognize": True, "start_height": 0.09}
DEFAULT_ARGS_END = {"end_height": 0.09, "rec_dir": 0, "rec_target_obs": False, "recfile": "plt/p0005.plt",
                    "recognize": False, "start_height": 0.2}
VS_DEFAULT = 1.539

def builtin_default():
    """Built-in template = the historical five-block RDS deadlock order."""
    vs = lambda: {"head": VS_DEFAULT, "tail": VS_DEFAULT}
    return {
        "name": "default", "title": "Default: pick-pre Wait / ForkLoad / Script / ForkUnload / ForkHeight",
        "version": 1, "pools": ["start", "end"],
        "steps": [
            {"id": "pre", "name": "前置Wait", "enabled": True, "blockSuffix": "-s_PRE",
             "location": {"type": "pre", "step": "s"}, "operation": "Wait", "args": {}, "vsOn": False, "variableShape": vs()},
            {"id": "s", "name": "取货", "enabled": True, "blockSuffix": "-s",
             "location": {"type": "pool", "pool": "start"}, "operation": "ForkLoad", "args": dict(DEFAULT_ARGS_START),
             "vsOn": False, "variableShape": vs()},
            {"id": "script", "name": "Script", "enabled": True, "blockSuffix": "-e_SCRIPT",
             "location": {"type": "pre", "step": "e"}, "operation": "Script",
             "args": {"script_name": "userpy/rec_retry_versatile.py",
                      "script_args": {"locName": "{end}", "operation": "locDetectMid70D", "recFile": "palletobject/p0001.palletobject"}},
             "vsOn": False, "variableShape": vs()},
            {"id": "e", "name": "放货", "enabled": True, "blockSuffix": "-e",
             "location": {"type": "pool", "pool": "end"}, "operation": "ForkUnload", "args": dict(DEFAULT_ARGS_END),
             "vsOn": True, "variableShape": vs()},
            {"id": "lift", "name": "升叉", "enabled": True, "blockSuffix": "-e_LIFT",
             "location": {"type": "pre", "step": "e"}, "operation": "ForkHeight", "args": {"end_height": 0.2},
             "vsOn": True, "variableShape": vs()},
        ],
    }

# ---------------------------------------------------------------- validation
NAME_RE = re.compile(r"^[A-Za-z0-9_.\-\u4e00-\u9fff]{1,64}$")

def validate(t):
    """Normalise a template in place and return a list of error strings (empty = ok)."""
    errs = []
    if not isinstance(t, dict): return ["template must be an object"]
    if not NAME_RE.match(str(t.get("name") or "")): errs.append("bad template name (letters/digits/_-. only)")
    steps = t.get("steps")
    if not isinstance(steps, list) or not steps: return errs + ["steps must be a non-empty list"]
    ids = set()
    for i, s in enumerate(steps):
        where = "step %d" % (i + 1)
        if not isinstance(s, dict): errs.append(where + ": must be an object"); continue
        sid = str(s.get("id") or "").strip()
        if not sid: sid = s["id"] = "step%d" % (i + 1)
        if sid in ids: errs.append(where + ": duplicate id " + sid)
        ids.add(sid)
        s.setdefault("name", sid); s.setdefault("enabled", True); s.setdefault("args", {}); s.setdefault("operation", "none")
        if not isinstance(s["args"], dict): errs.append(where + ": args must be an object")
        # migrate legacy args.m4Mode -> step.opMode (optional cleanup of the old key)
        if s.get("opMode") not in ("binTask", "operation"):
            am = s["args"].get("m4Mode") if isinstance(s.get("args"), dict) else None
            if am in ("binTask", "operation"):
                s["opMode"] = am
                if isinstance(s.get("args"), dict): s["args"].pop("m4Mode", None)
        elif isinstance(s.get("args"), dict) and s["args"].get("m4Mode") in ("binTask", "operation"):
            s["args"].pop("m4Mode", None)  # step.opMode wins; drop legacy duplicate
        if s.get("opMode") not in ("binTask", "operation", None):
            errs.append(where + ": opMode must be binTask or operation")
        loc = s.get("location")
        if not isinstance(loc, dict) or loc.get("type") not in ("pool", "pre", "fixed"):
            errs.append(where + ": location.type must be pool/pre/fixed"); continue
        if loc["type"] == "pool" and not loc.get("pool"): errs.append(where + ": location.pool missing")
        if loc["type"] == "fixed" and not loc.get("station"): errs.append(where + ": location.station missing")
        if loc["type"] == "pre" and (loc.get("select") or "nearest") != "nearest":
            e = check_sel(*sel_of(loc))
            if e: errs.append(where + ": " + e)
        vs = s.get("variableShape")
        if s.get("vsOn") and not (isinstance(vs, dict) and _num(vs.get("head")) is not None and _num(vs.get("tail")) is not None):
            errs.append(where + ": variableShape head/tail must be numbers")
        if "keepFinalPathSpace" in s and not isinstance(s["keepFinalPathSpace"], bool):
            errs.append(where + ": keepFinalPathSpace must be true/false")
    for i, s in enumerate(steps):
        loc = s.get("location") if isinstance(s, dict) else None
        if isinstance(loc, dict) and loc.get("type") == "pre" and resolve_step_ref(steps, loc.get("step")) is None:
            errs.append("step %d: location.step %r not found" % (i + 1, loc.get("step")))
    t.setdefault("version", 1)
    t["pools"] = pool_roles(t)  # only pools referenced by enabled steps
    return errs

def _num(v):
    try: return float(v)
    except Exception: return None

def resolve_step_ref(steps, ref):
    """step id, or 'stepN'/'N' (1-based index)"""
    if ref is None: return None
    ref = str(ref)
    for s in steps:
        if isinstance(s, dict) and str(s.get("id")) == ref: return s
    m = re.match(r"^(?:step)?(\d+)$", ref)
    if m and 1 <= int(m.group(1)) <= len(steps): return steps[int(m.group(1)) - 1]
    return None

def pool_roles(t, extra=()):
    """Pool names the template actually uses, in step order (this is also the pick order).
    A pool counts only if an enabled pool step uses it, or an enabled pre step derives from a (possibly
    disabled) pool step. Disabled steps alone do not make a pool required (e.g. end-only templates)."""
    steps = [s for s in (t.get("steps") or []) if isinstance(s, dict)]
    used = set()
    for s in steps:
        if not s.get("enabled", True): continue
        loc = s.get("location") or {}
        if loc.get("type") == "pool" and loc.get("pool"): used.add(loc["pool"])
        elif loc.get("type") == "pre":
            ref, seen = resolve_step_ref(steps, loc.get("step")), 0
            while ref is not None and (ref.get("location") or {}).get("type") == "pre" and seen < 20:
                ref = resolve_step_ref(steps, ref["location"].get("step")); seen += 1
            rl = (ref or {}).get("location") or {}
            if rl.get("type") == "pool" and rl.get("pool"): used.add(rl["pool"])
    out = []
    for s in steps:
        loc = s.get("location") or {}
        if loc.get("type") == "pool" and loc.get("pool") in used and loc["pool"] not in out: out.append(loc["pool"])
    for p in extra or []:
        if p and p not in out: out.append(p)
    return out

def used_pool_roles(t):
    return pool_roles(t)

# ---------------------------------------------------------------- pre-point selection
PRE_SELECT = ("nearest", "index", "name", "dir", "random")
# selArg: index -> 1-based candidate number; name -> exact name or wildcard (LM1*, *_A); dir -> in | out

def sel_of(loc):
    by = (loc or {}).get("select") or "nearest"; arg = (loc or {}).get("selArg")
    return by, ("" if arg is None else str(arg).strip())

def parse_sel(txt):
    """variable suffix after '@': nearest | random | in | out | #N | N | name=PATTERN | PATTERN -> (by, arg)"""
    t = (txt or "").strip()
    if not t or t == "nearest": return "nearest", ""
    if t == "random": return "random", ""
    if t in ("in", "out"): return "dir", t
    m = re.match(r"^#?(\d+)$", t)
    if m: return "index", m.group(1)
    if t.startswith("name="): return "name", t[5:]
    return "name", t

def check_sel(by, arg):
    if by not in PRE_SELECT: return "select must be one of " + "/".join(PRE_SELECT)
    if by == "index" and not (arg.isdigit() and int(arg) >= 1): return "select=index needs selArg = a number >= 1"
    if by == "dir" and arg not in ("in", "out"): return "select=dir needs selArg = in or out"
    if by == "name" and not arg: return "select=name needs selArg = a name or wildcard"
    return ""

def sel_label(by, arg):
    return by if by in ("nearest", "random") else "%s=%s" % (by, arg)

def pick_pre(cands, by, arg, rng=None):
    """cands: [{name, dir, dist, lm}] in preference order. Returns a name or ''."""
    if not cands: return ""
    if by == "nearest": return cands[0]["name"]
    if by == "index":
        i = int(arg) - 1; return cands[i]["name"] if 0 <= i < len(cands) else ""
    if by == "name":
        for c in cands:
            if c["name"] == arg or fnmatch.fnmatchcase(c["name"], arg): return c["name"]
        return ""
    if by == "dir":
        for c in cands:
            if c.get("dir") == arg: return c["name"]
        return ""
    if by == "random": return (rng or random).choice(cands)["name"]
    return ""

# ---------------------------------------------------------------- variables
VAR_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)(?::([^{}:]+))?\}")

class Ctx:
    def __init__(self, oid, picks, steps, locs, pre_of, roles, choose=None):
        self.oid, self.picks, self.steps, self.locs, self.pre_of, self.roles = oid, picks, steps, locs, pre_of, roles
        self.choose = choose; self.step = None
    def _pre(self, station, arg, what):
        """'<ref>@<selector>' -> pre-point by selector; plain -> legacy default (may be '')"""
        if arg is not None and "@" in arg and self.choose:
            by, sarg = parse_sel(arg.split("@", 1)[1])
            e = check_sel(by, sarg)
            if e: raise ValueError("{%s}: %s" % (what, e))
            if by != "nearest":
                where = "%s args {%s}" % ((self.step or {}).get("name") or (self.step or {}).get("id") or "?", what)
                return self.choose(station, by, sarg, where)
        return self.pre_of(station)
    def var(self, name, arg):
        if arg is None:
            if name in self.picks: return self.picks[name]
            if name == "orderId": return self.oid
            if name == "pickPre": return self.pre_of(self.picks.get(self._role("start", 0), ""))
            if name == "dropPre": return self.pre_of(self.picks.get(self._role("end", -1), ""))
            raise ValueError("unknown variable {%s}" % name)
        ref = arg.split("@", 1)[0].strip()
        if name == "pre": return self._pre(self.picks.get(ref, ""), arg, "pre:" + arg)
        if name in ("stationOf", "preOf"):
            s = resolve_step_ref(self.steps, ref)
            if s is None: raise ValueError("unknown step in {%s:%s}" % (name, arg))
            st = self.locs.get(s["id"], "")
            if name == "stationOf": return st
            loc = s.get("location") or {}
            return self._pre(self.base_station(s) if loc.get("type") != "pre" else st, arg, "preOf:" + arg)
        raise ValueError("unknown variable {%s:%s}" % (name, arg))
    def base_station(self, s):
        return self.locs.get(s["id"], "")
    def _role(self, want, idx):
        if want in self.roles: return want
        return self.roles[idx] if self.roles else want

def substitute(v, ctx):
    if isinstance(v, dict): return {k: substitute(x, ctx) for k, x in v.items()}
    if isinstance(v, list): return [substitute(x, ctx) for x in v]
    if isinstance(v, str) and "{" in v:
        return VAR_RE.sub(lambda m: str(ctx.var(m.group(1), m.group(2))), v)
    return v

# ---------------------------------------------------------------- build a neutral order
def build_order(t, picks, cfg, pre_of, oid=None, cands_of=None, rng=None, lenient=False):
    """picks: {pool name: station}. Returns a neutral order dict. ValueError if a needed pre-point is missing.
    pre_of(station) -> default pre-point; cands_of(station) -> [{name, dir, dist, lm}] for non-default selectors."""
    oid = oid or "dl-" + uuid.uuid4().hex[:12]
    steps = t["steps"]; roles = pool_roles(t)
    locs = {}; chosen = []; memo = {}
    def choose(station, by, arg, where):
        key = (station, by, arg)
        if key not in memo:
            cands = (cands_of(station) if cands_of else None)
            if cands is None: cands = [{"name": pre_of(station), "dir": None}] if pre_of(station) else []
            memo[key] = pick_pre(cands, by, arg, rng)
            if not memo[key] and lenient: memo[key] = "<pre:%s@%s>" % (station, sel_label(by, arg))
            if not memo[key]:
                names = ", ".join("%s(%s)" % (c["name"], c.get("dir") or "?") for c in cands) or "-"
                raise ValueError("步骤 %s: 站点 %s 没有符合 %s 的前置点 / no pre-point matches %s for station %s [step %s] (候选/candidates: %s)"
                                 % (where, station, sel_label(by, arg), sel_label(by, arg), station, where, names))
        chosen.append({"where": where, "station": station, "pre": memo[key], "select": sel_label(by, arg)})
        return memo[key]
    for s in steps:  # pool + fixed first (derived steps may point forwards)
        loc = s["location"]
        if loc["type"] == "pool": locs[s["id"]] = picks.get(loc["pool"], "")
        elif loc["type"] == "fixed": locs[s["id"]] = loc["station"]
    def resolve(s, depth=0):
        if s["id"] in locs: return locs[s["id"]]
        if depth > len(steps): raise ValueError("circular pre-point reference at step " + s["id"])
        ref = resolve_step_ref(steps, s["location"].get("step"))
        base = resolve(ref, depth + 1)
        by, arg = sel_of(s["location"])
        if by != "nearest":
            p = choose(base, by, arg, s.get("name") or s["id"])
        else:
            p = pre_of(base)
            if not p:
                what = ("%s(%s)" % (ref["location"]["pool"], ref.get("name") or ref["id"])) if ref["location"]["type"] == "pool" else (ref.get("name") or ref["id"])
                raise ValueError("%s %s 无前置点 / has no pre-point (scene derivation failed and no manual mapping) [step %s]" % (what, base, s.get("name") or s["id"]))
            chosen.append({"where": s.get("name") or s["id"], "station": base, "pre": p, "select": "nearest"})
        locs[s["id"]] = p
        return p
    out = []
    for s in steps:
        if not s.get("enabled", True): continue
        resolve(s)
    ctx = Ctx(oid, picks, steps, locs, pre_of, roles, choose)
    for s in steps:
        if not s.get("enabled", True): continue
        ctx.step = s
        st = {"id": s["id"], "name": s.get("name") or s["id"], "location": locs[s["id"]], "operation": s.get("operation") or "none",
              "args": substitute(copy.deepcopy(s.get("args") or {}), ctx), "suffix": s.get("blockSuffix") or ("-" + s["id"])}
        if s.get("opMode") in ("binTask", "operation"): st["opMode"] = s["opMode"]
        vs = s.get("variableShape")
        if s.get("vsOn") and isinstance(vs, dict) and vs.get("head") is not None and vs.get("tail") is not None:
            st["variableShape"] = {"head": float(vs["head"]), "tail": float(vs["tail"])}
        if s.get("keepFinalPathSpace") is True: st["keepFinalPathSpace"] = True
        out.append(st)
    o = {"id": oid, "template": t.get("name"), "picks": dict(picks), "steps": out, "preChosen": chosen,
         "priority": int(cfg.get("priority") or 1), "vehicle": cfg.get("vehicle") or "",
         "group": (cfg.get("group") or "").strip(), "label": (cfg.get("label") or "").strip()}
    return o

def needed_pre_roles(t):
    """{pool name} whose stations need a pre-point because an enabled 'pre' step derives from them."""
    need = set()
    for s in t["steps"]:
        if not s.get("enabled", True) or s["location"]["type"] != "pre": continue
        ref = resolve_step_ref(t["steps"], s["location"].get("step")); seen = 0
        while ref is not None and ref["location"]["type"] == "pre" and seen < 20:
            ref = resolve_step_ref(t["steps"], ref["location"].get("step")); seen += 1
        if ref is not None and ref["location"]["type"] == "pool": need.add(ref["location"]["pool"])
    return need

# ---------------------------------------------------------------- generation strategies
class RandomPicker:
    """Random pick per pool. no_reuse: sample without replacement inside a batch, reshuffle when exhausted.
    no_self: a station is not used twice in one order. (Same random-call sequence as the legacy Picker.)"""
    def __init__(self, pools, no_self=True, no_reuse=True, rng=None):
        self.pools = [(k, list(v)) for k, v in pools]; self.no_self, self.no_reuse = no_self, no_reuse
        self.rem = {k: [] for k, _ in self.pools}; self.rng = rng or random
    def _take(self, rem, full, excl):
        r = self.rng
        if not self.no_reuse:
            c = [x for x in full if x not in excl] or full; return r.choice(c)
        if not [x for x in rem if x not in excl]: rem.extend(r.sample(full, len(full)))
        c = [i for i, x in enumerate(rem) if x not in excl]
        if not c: return r.choice(full)
        return rem.pop(r.choice(c))
    def next(self):
        picks = {}
        for k, full in self.pools:
            picks[k] = self._take(self.rem[k], full, set(picks.values()) if self.no_self else set())
        return picks
    def default_count(self): return len(self.pools[0][1]) if self.pools else 0

class RoundRobinPicker:
    """Order i takes element i % len(pool) of every pool (skips forward to avoid a repeated station if no_self)."""
    def __init__(self, pools, no_self=True, **_):
        self.pools = [(k, list(v)) for k, v in pools]; self.no_self = no_self; self.i = 0
    def next(self):
        picks = {}
        for k, full in self.pools:
            for j in range(len(full)):
                x = full[(self.i + j) % len(full)]
                if not self.no_self or x not in picks.values(): break
            picks[k] = x
        self.i += 1
        return picks
    def default_count(self): return max((len(v) for _, v in self.pools), default=0)

class CartesianPicker:
    """Every combination once (pools in pick order); combos repeating a station are skipped if no_self. Cycles."""
    def __init__(self, pools, no_self=True, **_):
        self.keys = [k for k, _ in pools]
        self.combos = [c for c in itertools.product(*[v for _, v in pools]) if not no_self or len(set(c)) == len(c)]
        self.i = 0
    def next(self):
        if not self.combos: raise ValueError("no valid combination")
        c = self.combos[self.i % len(self.combos)]; self.i += 1
        return dict(zip(self.keys, c))
    def default_count(self): return len(self.combos)

STRATEGIES = {"random": RandomPicker, "round_robin": RoundRobinPicker, "cartesian": CartesianPicker}

def make_picker(strategy, pools, no_self=True, no_reuse=True, rng=None):
    cls = STRATEGIES.get(strategy or "random")
    if cls is None: raise ValueError("unknown strategy " + str(strategy))
    return cls(pools, no_self=no_self, no_reuse=no_reuse, rng=rng)

# ---------------------------------------------------------------- storage
class Store:
    def __init__(self, folder):
        self.dir = folder; os.makedirs(folder, exist_ok=True)
    def path(self, name):
        if not NAME_RE.match(name or ""): raise ValueError("bad template name")
        return os.path.join(self.dir, name + ".json")
    def names(self):
        return sorted(f[:-5] for f in os.listdir(self.dir) if f.endswith(".json") and NAME_RE.match(f[:-5]))
    def get(self, name):
        try:
            with open(self.path(name), encoding="utf-8-sig") as f: t = json.load(f)
        except (OSError, ValueError):
            return builtin_default() if name == "default" else None
        t["name"] = name; validate(t)
        return t
    def put(self, t):
        errs = validate(t)
        if errs: raise ValueError("; ".join(errs))
        p = self.path(t["name"]); tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(t, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p); return t
    def delete(self, name):
        # empty template list is allowed (user may delete all; add_server seeds once at create)
        if name not in self.names(): raise ValueError("template not found")
        os.remove(self.path(name))
    def rename(self, old, new, overwrite=False):
        if not NAME_RE.match(old or "") or not NAME_RE.match(new or ""): raise ValueError("bad template name")
        if old == new: return self.get(old)
        if old not in self.names(): raise ValueError("template not found")
        if new in self.names() and not overwrite: raise ValueError("template exists")
        t = self.get(old); t["name"] = new; self.put(t); os.remove(self.path(old)); return t

# ---------------------------------------------------------------- legacy migration
def from_legacy_cfg(cfg):
    """Legacy request/settings (startOp/startArgs/.../scriptOn/liftOn/vsPerBlock) -> template.
    Reproduces the old build_order() exactly."""
    t = builtin_default(); S = {s["id"]: s for s in t["steps"]}
    S["pre"]["enabled"] = bool(cfg.get("pickPreOn"))
    S["s"]["operation"] = cfg.get("startOp") or "none"
    S["s"]["args"] = cfg.get("startArgs") if isinstance(cfg.get("startArgs"), dict) else {}
    S["e"]["operation"] = cfg.get("endOp") or "none"
    S["e"]["args"] = cfg.get("endArgs") if isinstance(cfg.get("endArgs"), dict) else {}
    S["script"]["enabled"] = bool(cfg.get("scriptOn"))
    S["script"]["args"] = {"script_name": cfg.get("scriptName") or "userpy/rec_retry_versatile.py",
                           "script_args": {"locName": "{end}", "operation": cfg.get("scriptOp") or "locDetectMid70D", "recFile": cfg.get("scriptRecFile") or ""}}
    S["lift"]["enabled"] = bool(cfg.get("liftOn"))
    S["lift"]["operation"] = cfg.get("liftOp") or "ForkHeight"
    S["lift"]["args"] = cfg.get("liftArgs") if isinstance(cfg.get("liftArgs"), dict) else {"end_height": 0.2}
    pb = cfg.get("vsPerBlock")
    for r, s in S.items():
        s["vsOn"] = False
        if isinstance(pb, dict):
            v = pb.get(r)
            if isinstance(v, dict) and v.get("head") is not None and v.get("tail") is not None and v.get("on", True):
                s["vsOn"] = True; s["variableShape"] = {"head": float(v["head"]), "tail": float(v["tail"])}
            elif isinstance(v, dict) and _num(v.get("head")) is not None and _num(v.get("tail")) is not None:
                s["variableShape"] = {"head": _num(v["head"]), "tail": _num(v["tail"])}
        else:
            vs = cfg.get("variableShape"); vsb = cfg.get("vsBlocks") if isinstance(cfg.get("vsBlocks"), list) else ["e", "lift"]
            if vs and r in vsb:
                s["vsOn"] = True; s["variableShape"] = vs  # legacy global value, copied as-is
    return t

def _jsonobj(txt, dflt):
    if isinstance(txt, dict): return txt
    try:
        v = json.loads(txt) if isinstance(txt, str) and txt.strip() else None
        return v if isinstance(v, dict) else dflt
    except ValueError: return dflt

def from_legacy_settings(st):
    """settings.json written by rds_tester.py (fields = raw UI inputs) -> template, or None if nothing to migrate."""
    f = st.get("fields") if isinstance(st.get("fields"), dict) else None
    if f is None and not isinstance(st.get("vsPerBlock"), dict): return None
    f = f or {}
    on = lambda k, d: bool(f[k]) if k in f else d
    pb = st.get("vsPerBlock")
    if isinstance(pb, dict):
        pb = {r: v for r, v in pb.items() if isinstance(v, dict)}
        pb = {r: dict(v, head=_num(v.get("head")) if _num(v.get("head")) is not None else VS_DEFAULT,
                      tail=_num(v.get("tail")) if _num(v.get("tail")) is not None else VS_DEFAULT) for r, v in pb.items()}
    cfg = {"pickPreOn": on("pre_on", True), "startOp": f.get("st_op") or "ForkLoad", "startArgs": _jsonobj(f.get("st_args"), dict(DEFAULT_ARGS_START)),
           "endOp": f.get("en_op") or "ForkUnload", "endArgs": _jsonobj(f.get("en_args"), dict(DEFAULT_ARGS_END)),
           "scriptOn": on("scr_on", True), "scriptName": f.get("scr_name") or "userpy/rec_retry_versatile.py",
           "scriptOp": f.get("scr_op") or "locDetectMid70D", "scriptRecFile": f.get("scr_rec", "palletobject/p0001.palletobject"),
           "liftOn": on("lift_on", True), "liftOp": f.get("lift_op") or "ForkHeight", "liftArgs": _jsonobj(f.get("lift_args"), {"end_height": 0.2}),
           "vsPerBlock": pb if isinstance(pb, dict) else {"e": {"on": True, "head": VS_DEFAULT, "tail": VS_DEFAULT}, "lift": {"on": True, "head": VS_DEFAULT, "tail": VS_DEFAULT}}}
    t = from_legacy_cfg(cfg)
    # keep remembered head/tail of disabled roles
    for s in t["steps"]:
        v = (cfg["vsPerBlock"] or {}).get(s["id"])
        if isinstance(v, dict) and not s["vsOn"]: s["variableShape"] = {"head": v["head"], "tail": v["tail"]}
    t["title"] = "Migrated from legacy settings.json"
    return t
