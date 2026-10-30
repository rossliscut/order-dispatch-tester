# -*- coding: utf-8 -*-
"""M4 (Seer M4 fleet) adapter. RDS block = M4 step, RDS complete = M4 stepFixed.
  create  POST /api/fleet/orders/create {id, sceneId, stepFixed, steps:[{id, location, rbkArgs, forLoad, forUnload}], ...}
  append  POST /api/fleet/orders/add-steps {orderId, steps}
  seal    POST /api/fleet/orders/complete-order {orderId}
  detail  GET  /api/fleet/orders/query-order-detail?orderId=
  cancel  POST /api/fleet/orders/cancel {sceneId, orderId}
  robots  GET  /api/fleet/robots/all-all?sceneId=
  scenes  GET  /api/fleet/scenes/list ; map: GET /api/fleet/scenes/schema/{sceneId}
  smap    GET  /api/fleet/scenes/{sceneId}/download/{mapFile}  (UI link for groupsMap.mapFile)
Success = HTTP 200 (body is the result itself, may be empty). Errors: 400 {code, message}, 401, 403.
Auth: headers xyy-app-id / xyy-app-key, or POST /api/sign-in {username, password} (session cookie kept in a jar).
Credentials come from the UI (settings.json, gitignored) or env vars ODT_M4_APP_ID / ODT_M4_APP_KEY / ODT_M4_USER /
ODT_M4_PASSWORD / ODT_M4_SCENE. They are never logged.

Status mapping to the core's internal (RDS-style) states, so core.py needs no M4 knowledge:
  Done -> FINISHED, Cancelled -> STOPPED          (the ONLY terminal states)
  fault:true (any non-terminal status) -> FAILED  (pause only, keeps polling/appending)
  ToBeAllocated -> TOBEDISPATCHED, Allocated -> CREATED, Executing -> RUNNING,
  Pending -> WAITING if not sealed else RUNNING, Cancelling / Withdrawing / unknown -> passed through upper-cased
  (non-terminal, never stops appending). Raw values are kept in m4Status / fault / faultReason.
Step: Done -> FINISHED, Cancelled -> STOPPED, Executing -> RUNNING, Executable -> CREATED, other -> raw."""
import http.cookiejar, io, json, os, time, urllib.parse, urllib.request, urllib.error, zipfile
from .base import DispatcherAdapter
from . import m4_scene, rds_scene

ORDER_MAP = {"Done": "FINISHED", "Cancelled": "STOPPED", "ToBeAllocated": "TOBEDISPATCHED", "Allocated": "CREATED", "Executing": "RUNNING"}
STEP_MAP = {"Done": "FINISHED", "Cancelled": "STOPPED", "Executing": "RUNNING", "Executable": "CREATED"}
SECRET_KEYS = ("appKey", "password")
MASK = "******"
STEP_KEYS = ("m4Mode", "m4BinTask", "forLoad", "forUnload")  # per-step adapter hints inside step args (not sent in rbkArgs)

def mask(d):
    """copy of an options/profile dict with secrets replaced by MASK (empty stays empty)"""
    return {k: (MASK if k in SECRET_KEYS and v else v) for k, v in (d or {}).items()}

def as_bool(v):
    if isinstance(v, str): return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)

def as_int(v, d=None):
    try: return int(float(v))
    except (TypeError, ValueError): return d

def as_obj(v):
    """rbkArgs etc. may arrive as JSON text"""
    if isinstance(v, dict): return v
    if isinstance(v, str) and v.strip():
        try:
            r = json.loads(v)
            return r if isinstance(r, dict) else {}
        except ValueError: return {}
    return {}

def map_order_state(js):
    st = js.get("status")
    if st in ("Done", "Cancelled"): return ORDER_MAP[st]
    if as_bool(js.get("fault")): return "FAILED"
    if st == "Pending": return "RUNNING" if as_bool(js.get("stepFixed")) else "WAITING"
    if st in ORDER_MAP: return ORDER_MAP[st]
    return str(st).upper() if st else None

class M4Adapter(DispatcherAdapter):
    name = "m4"
    terminal_states = frozenset({"FINISHED", "STOPPED"})  # = M4 Done / Cancelled
    base_from_settings = False  # base URL comes from the M4 profile, not the RDS base field
    supports_incremental = True

    def __init__(self, base_url, log=None, opts=None):
        DispatcherAdapter.__init__(self, base_url, log)
        self.opts = {}
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.configure(opts or {})

    def configure(self, opts):
        e = os.environ.get
        o = dict(opts or {})
        self.opts = {"sceneId": o.get("sceneId") or e("ODT_M4_SCENE", ""), "appId": o.get("appId") or e("ODT_M4_APP_ID", ""),
                     "appKey": o.get("appKey") or e("ODT_M4_APP_KEY", ""), "username": o.get("username") or e("ODT_M4_USER", ""),
                     "password": o.get("password") or e("ODT_M4_PASSWORD", ""), "opMode": o.get("opMode") or "binTask",
                     "auth": o.get("auth") or ""}
        if o.get("base"): self.base = o["base"]
        self.jar.clear(); self._signed = False; self._last_scene = None

    @property
    def scene_id(self): return self.opts.get("sceneId") or ""

    def auth_mode(self):
        a = self.opts.get("auth")
        if a in ("appkey", "login", "none"): return a
        if self.opts.get("appId") and self.opts.get("appKey"): return "appkey"
        if self.opts.get("username"): return "login"
        return "none"

    # ------------------------------------------------------------ payload
    def step_mode(self, st, hint=None):
        """Per-step binTask|operation. Prefer step.opMode, then legacy args.m4Mode, then profile opMode, else binTask."""
        hint = hint or {}
        m = st.get("opMode") or hint.get("m4Mode") or self.opts.get("opMode") or "binTask"
        return m if m in ("binTask", "operation") else "binTask"

    def build_step(self, order, st):
        args = dict(st.get("args") if isinstance(st.get("args"), dict) else {})
        hint = {k: args.pop(k) for k in STEP_KEYS if k in args}
        op = st.get("operation"); mode = self.step_mode(st, hint)
        s = {"id": order["id"] + st["suffix"], "location": st["location"]}
        if op == "Script":
            rb = {"operation": "Script", "script_name": args.pop("script_name", ""), "script_args": args.pop("script_args", {})}
            rb.update(args); s["rbkArgs"] = rb
        elif op and op != "none":
            if mode == "operation":
                rb = {"operation": op}; rb.update(args)
            else:
                rb = {"binTask": hint.get("m4BinTask") or op}  # binTask: action name only, no ordinary args
            s["rbkArgs"] = rb
        low = str(hint.get("m4BinTask") or op or "").lower()
        unload = "unload" in low; load = not unload and "load" in low
        s["forLoad"] = as_bool(hint["forLoad"]) if "forLoad" in hint else load
        s["forUnload"] = as_bool(hint["forUnload"]) if "forUnload" in hint else unload
        if st.get("keepFinalPathSpace") is True: s["keepFinalPathSpace"] = True  # 保持末段空间资源不释放
        return s

    def build_payload(self, order):
        o = {"id": order["id"], "sceneId": self.scene_id, "priority": int(order.get("priority") or 1), "stepFixed": True,
             "steps": [self.build_step(order, st) for st in order["steps"]]}
        if order.get("vehicle"): o["expectedRobotNames"] = [order["vehicle"]]
        if (order.get("group") or "").strip(): o["expectedRobotGroups"] = [order["group"].strip()]
        if (order.get("label") or "").strip(): o["externalId"] = order["label"].strip()
        return o

    # ------------------------------------------------------------ http
    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.auth_mode() == "appkey": h["xyy-app-id"] = self.opts["appId"]; h["xyy-app-key"] = self.opts["appKey"]
        return h

    def _raw(self, method, path, body, timeout):
        url = self.base.rstrip("/") + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers=self._headers())
        try:
            with self.opener.open(req, timeout=timeout) as r: return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e: return e.code, e.read().decode("utf-8", "replace")
        except Exception as e: return None, "ERR " + str(e)

    def sign_in(self, timeout=8):
        st, txt = self._raw("POST", "/api/sign-in", {"username": self.opts.get("username", ""), "password": self.opts.get("password", "")}, timeout)
        self._signed = st == 200
        self.log("http", method="POST", url=self.base.rstrip("/") + "/api/sign-in", req={"username": self.opts.get("username", ""), "password": MASK},
                 status=st, resp="(signed in)" if self._signed else txt[:300])
        return self._signed, None if self._signed else "sign-in HTTP %s %s" % (st, txt[:200])

    def request(self, method, path, body=None, timeout=8, quiet=False):
        t0 = time.time()
        if self.auth_mode() == "login" and not self._signed: self.sign_in(timeout)
        status, txt = self._raw(method, path, body, timeout)
        if status == 401 and self.auth_mode() == "login":  # session expired: sign in once more and retry
            if self.sign_in(timeout)[0]: status, txt = self._raw(method, path, body, timeout)
        try: js = json.loads(txt) if txt.strip() else None
        except ValueError: js = None
        if not quiet or method != "GET":
            self.log("http", method=method, url=self.base.rstrip("/") + path, req=body, status=status, ms=int((time.time() - t0) * 1000), resp=js if js is not None else txt[:2000])
        return status, js, txt

    @staticmethod
    def _ok(st, js, txt):
        if st == 200: return True, None
        m = js.get("message") if isinstance(js, dict) else None
        return False, "HTTP %s %s" % (st, m or txt[:200])

    def ping(self):
        st, js, txt = self.request("GET", "/api/ping", quiet=True)
        return st == 200, js if js is not None else txt[:200]

    def scenes(self):
        st, js, _ = self.request("GET", "/api/fleet/scenes/list", quiet=True)
        if st != 200 or not isinstance(js, list): return None
        return [{"id": str(s.get("id")), "name": s.get("name") or "", "disabled": bool(s.get("disabled"))} for s in js if isinstance(s, dict) and s.get("id") is not None]

    # ------------------------------------------------------------ orders
    def submit(self, payload):
        if not payload.get("sceneId"): return False, "M4 sceneId not configured"
        return self._ok(*self.request("POST", "/api/fleet/orders/create", payload))

    def order_status(self, order_id, quiet=True, timeout=8):
        st, js, txt = self.request("GET", "/api/fleet/orders/query-order-detail?orderId=" + urllib.parse.quote(order_id), timeout=timeout, quiet=quiet)
        if st == 400 and isinstance(js, dict):
            m = str(js.get("message") or "")
            if any(k in m.lower() for k in ("not found", "not exist", "no such")) or "不存在" in m or "找不到" in m:
                return {"missing": True, "msg": m or str(js.get("code"))}
            return None
        if st != 200 or not isinstance(js, dict) or not (js.get("id") or js.get("status")): return None
        steps = [s for s in (js.get("steps") or []) if isinstance(s, dict)]
        steps.sort(key=lambda s: as_int(s.get("stepIndex"), 1 << 30))
        sts = []; ids = []
        for i, s in enumerate(steps):
            raw = s.get("status"); sts.append(STEP_MAP.get(raw, raw)); ids.append(s.get("id") or "%s-Step%d" % (order_id, as_int(s.get("stepIndex"), i)))
            s["rbkArgs"] = as_obj(s.get("rbkArgs"))
        return {"state": map_order_state(js), "m4Status": js.get("status"), "fault": as_bool(js.get("fault")), "faultReason": js.get("faultReason") or "",
                "vehicle": js.get("actualRobotName") or "", "blockStates": sts, "blockIds": ids, "complete": as_bool(js.get("stepFixed")),
                "blockStartTimes": [t for t in (ms_ts(s.get("startOn")) for s in steps) if t],
                "createTime": ms_ts(js.get("createdOn")), "receiveTime": None,
                "terminateTime": ms_ts(js.get("doneOn")) if js.get("status") == "Cancelled" else None,
                "finishTime": ms_ts(js.get("doneOn")) if js.get("status") == "Done" else None}

    def incremental_payload(self, payload, n):
        return dict(payload, stepFixed=False, steps=list(payload["steps"][:n]))
    def payload_blocks(self, payload): return list(payload.get("steps") or [])
    def block_id(self, block): return block.get("id")
    def add_blocks(self, order_id, blocks, complete=False):
        ok, err = self._ok(*self.request("POST", "/api/fleet/orders/add-steps", {"orderId": order_id, "steps": blocks}))
        if ok and complete: return self.mark_complete(order_id)  # M4 has no combined add+seal call
        return ok, err
    def mark_complete(self, order_id):
        return self._ok(*self.request("POST", "/api/fleet/orders/complete-order", {"orderId": order_id}))
    def cancel(self, order_id):
        st, js, txt = self.request("POST", "/api/fleet/orders/cancel", {"sceneId": self.scene_id, "orderId": order_id})
        return js if js is not None else {"status": st, "text": txt[:200]}

    # ------------------------------------------------------------ fleet
    def robots(self):
        if not self.scene_id: return None
        st, js, _ = self.request("GET", "/api/fleet/robots/all-all?sceneId=" + urllib.parse.quote(self.scene_id), quiet=True)
        if st != 200 or not isinstance(js, dict): return None
        out = []
        for k, r in js.items():
            if not isinstance(r, dict): continue
            orders = r.get("orders") if isinstance(r.get("orders"), list) else []
            cur = orders[0] if orders else ""
            if isinstance(cur, dict): cur = cur.get("id") or cur.get("orderId") or ""
            out.append({"name": r.get("name") or k, "x": r.get("x"), "y": r.get("y"), "angle": r.get("d"), "station": r.get("p") or "",
                        "order": str(cur or ""), "orderState": None, "group": r.get("groupName") or "",
                        "dispatchable": not (r.get("disabled") or r.get("offDuty")), "connected": r.get("online"),
                        "blocked": r.get("blocked"), "battery": r.get("battery")})
        return out

    # ------------------------------------------------------------ scene
    def scene(self, progress=None):
        prog = progress or (lambda *a, **k: None)
        if not self.scene_id: return None, None, "M4 sceneId not configured"
        prog("request")
        st, js, txt = self.request("GET", "/api/fleet/scenes/schema/" + urllib.parse.quote(self.scene_id), timeout=90, quiet=True)
        if st != 200: return st, None, txt
        if not isinstance(js, dict): return st, None, "invalid JSON: " + txt[:200]
        self._last_scene = js
        return st, js, txt
    def parse_stations(self, scene): return m4_scene.parse_scene(scene)
    def parse_groups(self, scene): return m4_scene.parse_groups(scene)
    def extract_geom(self, scene, points_only=False): return m4_scene.extract_geom(scene, points_only)
    def decode_map(self, raw): return rds_scene.decode_smap(raw)

    def _map_file_records(self, js):
        """Unique (mapName, mapFile) from structure.areas[].groupsMap (skips disabled areas)."""
        out, seen = [], set()
        for area in ((js or {}).get("structure") or {}).get("areas") or []:
            if not isinstance(area, dict) or area.get("disabled"): continue
            gm = area.get("groupsMap")
            if not isinstance(gm, dict): continue
            for rec in gm.values():
                if not isinstance(rec, dict): continue
                mf = (rec.get("mapFile") or "").strip()
                if not mf or mf in seen: continue
                seen.add(mf)
                mn = (rec.get("mapName") or os.path.basename(mf) or "map.smap").strip()
                if not mn.lower().endswith(".smap"): mn += ".smap"
                out.append((mn, mf))
        return out

    def _get_bytes(self, path, timeout, progress=None):
        """Authenticated binary GET (for .smap download). Returns (status, bytes)."""
        prog = progress or (lambda *a, **k: None)
        if self.auth_mode() == "login" and not self._signed: self.sign_in(timeout)
        url = self.base.rstrip("/") + path
        req = urllib.request.Request(url, method="GET", headers=self._headers())
        try:
            with self.opener.open(req, timeout=timeout) as r:
                try: total = int(r.headers.get("Content-Length") or 0) or None
                except ValueError: total = None
                buf = bytearray(); prog("mapdl", 0, total)
                while True:
                    c = r.read1(262144) if hasattr(r, "read1") else r.read(262144)
                    if not c: break
                    buf += c; prog("mapdl", len(buf), total)
                return r.status, bytes(buf)
        except urllib.error.HTTPError as e:
            if e.code == 401 and self.auth_mode() == "login" and self.sign_in(timeout)[0]:
                return self._get_bytes(path, timeout, progress)
            return e.code, b""
        except Exception as e:
            return None, str(e).encode()

    def download_maps(self, timeout=120, progress=None):
        """(status, zip-bytes) of scene .smap files.

        M4 UI downloads each ``groupsMap.*.mapFile`` via
        ``GET /api/fleet/scenes/{sceneId}/download/{mapFile}`` (not ``/api/files/get``).
        When the schema has no ``normalPosList``, core uses this the same way as RDS ``/downloadScene``.
        """
        prog = progress or (lambda *a, **k: None)
        if not self.scene_id: return None, b""
        js = getattr(self, "_last_scene", None)
        if not isinstance(js, dict):
            st, js, _ = self.scene(progress=prog)
            if st != 200 or not isinstance(js, dict): return st, b""
        files = self._map_file_records(js)
        if not files: return 404, b""
        sid = urllib.parse.quote(self.scene_id, safe="")
        packed = io.BytesIO()
        n_ok = 0
        with zipfile.ZipFile(packed, "w", zipfile.ZIP_STORED) as zf:
            for mn, mf in files:
                # Keep slashes in mapFile (UI: `/api/fleet/scenes/${id}/download/${mapFile}`)
                path = "/api/fleet/scenes/%s/download/%s" % (sid, urllib.parse.quote(mf, safe="/"))
                st, raw = self._get_bytes(path, timeout, progress=prog)
                if st != 200 or not raw:
                    self.log("http", method="GET", url=self.base.rstrip("/") + path, status=st, resp="(map download %d bytes)" % len(raw or b""))
                    continue
                # Avoid colliding basenames when several groups share a mapName
                name = mn if mn not in zf.namelist() else ("%s_%s" % (n_ok, mn))
                zf.writestr(name, raw); n_ok += 1
                self.log("http", method="GET", url=self.base.rstrip("/") + path, status=st, resp="(map %s %d bytes)" % (name, len(raw)))
        if not n_ok: return 404, b""
        return 200, packed.getvalue()

    def raw_get(self, path): return self.request("GET", path, quiet=True)

def ms_ts(v):
    """M4 times are Unix ms -> epoch seconds or None"""
    try: v = float(v)
    except (TypeError, ValueError): return None
    if v > 1e12: v /= 1000.0
    return v if v > 1e9 else None
