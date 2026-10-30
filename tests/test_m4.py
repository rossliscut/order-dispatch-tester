# -*- coding: utf-8 -*-
"""M4 adapter against tools/fake_m4.py (mock data only): payload, auth, status mapping, scene parsing,
block-by-block (create stepFixed=false + add-steps + complete-order), fault pauses then recovers, Done/Cancelled stop."""
import json, os, sys, time, unittest, urllib.request
from helpers import C, fresh_core, ROOT, PREPOINTS
sys.path.insert(0, os.path.join(ROOT, "tools"))
import fake_m4
from order_tester import server, templates as T
from order_tester.adapters import m4 as M4

class Base(unittest.TestCase):
    auth = {"appId": fake_m4.APP_ID, "appKey": fake_m4.APP_KEY}
    def setUp(self):
        self.srv = fake_m4.serve(0); self.addCleanup(self.srv.shutdown)
        self.url = "http://127.0.0.1:%d" % self.srv.server_address[1]
        fresh_core(self)
        C.m4_save("mock", dict(self.auth, base=self.url, sceneId=fake_m4.SCENE_ID)); C.save_settings({"adapter": "m4"}); C.set_adapter("m4")
        C.S["prepoints"] = dict(PREPOINTS); C.S["cfg"] = {"pollSec": 0.3, "incPollSec": 0.1}
        with fake_m4.LOCK: fake_m4.ORDERS.clear(); del fake_m4.RECEIVED[:]; del fake_m4.EVENTS[:]
        self.addCleanup(setattr, fake_m4, "STEP_DUR", fake_m4.STEP_DUR); fake_m4.STEP_DUR = 0.3
        self.t = T.builtin_default(); T.validate(self.t)
    def draft(self, oid, a="AP1", b="AP2", cfg=None):
        rec = C.make_draft({"start": a, "end": b}, self.t, cfg or {}, oid)
        with C.lock: C.S["orders"][oid] = rec
        return rec
    def run_until(self, pred, limit=15, also=None):
        t0 = time.time()
        while time.time() - t0 < limit:
            C.inc_once()
            if also: also()
            if pred(): return True
            time.sleep(0.05)
        return False

class AdapterTest(Base):
    def test_selected_and_default_rds(self):
        self.assertEqual(C.AD().name, "m4"); self.assertEqual(C.AD().base, self.url)
        C.save_settings({"adapter": "rds"}); C.set_adapter("rds"); self.assertEqual(C.AD().name, "rds")
        d = fresh_core(self); self.assertEqual(C.AD().name, "rds")  # fresh install defaults to RDS

    def test_payload_bintask_default_and_override(self):
        rec = self.draft("m4-pay1"); b = rec["body"]
        self.assertEqual(b["sceneId"], fake_m4.SCENE_ID); self.assertIs(b["stepFixed"], True)
        self.assertEqual([s["id"] for s in b["steps"]], ["m4-pay1" + (s.get("blockSuffix") or "-" + s["id"]) for s in self.t["steps"] if s.get("enabled", True)])
        load = [s for s in b["steps"] if s.get("rbkArgs", {}).get("binTask") == "ForkLoad"][0]
        self.assertEqual(load["rbkArgs"], {"binTask": "ForkLoad"})  # binTask: name only, no merged args
        self.assertTrue(load["forLoad"]); self.assertFalse(load["forUnload"])
        unl = [s for s in b["steps"] if s.get("rbkArgs", {}).get("binTask") == "ForkUnload"][0]
        self.assertEqual(unl["rbkArgs"], {"binTask": "ForkUnload"})
        self.assertTrue(unl["forUnload"]); self.assertFalse(unl["forLoad"])
        scr = [s for s in b["steps"] if s.get("rbkArgs", {}).get("operation") == "Script"][0]
        self.assertIn("script_name", scr["rbkArgs"])
        ad = C.AD()
        # legacy args.m4Mode still works
        st = {"id": "x", "suffix": "-x", "location": "AP1", "operation": "ForkLoad", "args": {"m4Mode": "operation", "end_height": 0.1}}
        s = ad.build_step({"id": "o"}, st)
        self.assertEqual(s["rbkArgs"], {"operation": "ForkLoad", "end_height": 0.1}); self.assertTrue(s["forLoad"])
        # step.opMode preferred; binTask ignores ordinary args
        s = ad.build_step({"id": "o"}, {"id": "x", "suffix": "-x", "location": "AP1", "operation": "ForkLoad",
                                       "opMode": "binTask", "args": {"end_height": 0.1, "m4BinTask": "Load", "forLoad": False}})
        self.assertEqual(s["rbkArgs"], {"binTask": "Load"}); self.assertFalse(s["forLoad"])
        s = ad.build_step({"id": "o"}, {"id": "x", "suffix": "-x", "location": "AP1", "operation": "ForkLoad",
                                       "opMode": "operation", "args": {"end_height": 0.2}})
        self.assertEqual(s["rbkArgs"], {"operation": "ForkLoad", "end_height": 0.2})
        # profile opMode fallback when step has neither opMode nor m4Mode
        ad.configure(dict(C.m4_profile(), opMode="operation"))
        self.assertEqual(ad.build_step({"id": "o"}, dict(st, args={}))["rbkArgs"], {"operation": "ForkLoad"})

    def test_keep_final_path_space(self):
        # per-step 保持末段空间资源不释放: checked -> keepFinalPathSpace true; unchecked/missing -> not sent
        t = T.builtin_default(); end = [s for s in t["steps"] if s["id"] == "e"][0]; end["keepFinalPathSpace"] = True
        T.validate(t)
        b = C.make_draft({"start": "AP1", "end": "AP2"}, t, {}, "m4-kfs")["body"]
        on = [s for s in b["steps"] if s.get("keepFinalPathSpace")]
        self.assertEqual([s["id"] for s in on], ["m4-kfs" + (end.get("blockSuffix") or "-e")]); self.assertIs(on[0]["keepFinalPathSpace"], True)
        self.assertEqual(sum("keepFinalPathSpace" in s for s in b["steps"]), 1)
        ok, err = C.AD().submit(b); self.assertTrue(ok, err)
        with fake_m4.LOCK: got = fake_m4.RECEIVED[-1]
        self.assertEqual([s.get("keepFinalPathSpace") for s in got["steps"]].count(True), 1)
        end["keepFinalPathSpace"] = "yes"; self.assertTrue(any("keepFinalPathSpace" in e for e in T.validate(t)))  # must be a bool
        end["keepFinalPathSpace"] = True
        C.save_settings({"adapter": "rds"}); C.set_adapter("rds"); C.S["prepoints"] = dict(PREPOINTS)  # RDS ignores it
        self.assertNotIn("keepFinalPathSpace", json.dumps(C.make_draft({"start": "AP1", "end": "AP2"}, t, {}, "rds-kfs")["body"]))

    def test_mixed_opmode_in_one_order(self):
        ad = C.AD()
        steps = [
            {"id": "a", "suffix": "-a", "location": "AP1", "operation": "ForkLoad", "opMode": "binTask", "args": {"end_height": 0.1}},
            {"id": "b", "suffix": "-b", "location": "AP2", "operation": "ForkUnload", "opMode": "operation", "args": {"end_height": 0.09}},
            {"id": "c", "suffix": "-c", "location": "LM2", "operation": "Script", "opMode": "binTask",
             "args": {"script_name": "s.py", "script_args": {"x": 1}}},
        ]
        body = ad.build_payload({"id": "mix1", "steps": steps, "priority": 1})
        self.assertEqual(body["steps"][0]["rbkArgs"], {"binTask": "ForkLoad"})
        self.assertEqual(body["steps"][1]["rbkArgs"], {"operation": "ForkUnload", "end_height": 0.09})
        self.assertEqual(body["steps"][2]["rbkArgs"]["operation"], "Script")
        self.assertEqual(body["steps"][2]["rbkArgs"]["script_name"], "s.py")

    def test_auth_appkey_login_and_401(self):
        ad = C.AD(); self.assertEqual(ad.auth_mode(), "appkey"); self.assertTrue(ad.ping()[0])
        bad = M4.M4Adapter(self.url, None, {"sceneId": "scene-1"}); self.assertFalse(bad.ping()[0]); self.assertIsNone(bad.order_status("x"))
        lg = M4.M4Adapter(self.url, None, {"username": fake_m4.USER, "password": fake_m4.PASSWORD, "sceneId": "scene-1"})
        self.assertEqual(lg.auth_mode(), "login"); self.assertTrue(lg.ping()[0]); self.assertEqual(lg.scenes()[0]["id"], "scene-1")
        wrong = M4.M4Adapter(self.url, None, {"username": fake_m4.USER, "password": "nope"}); self.assertFalse(wrong.ping()[0])

    def test_secrets_masked_in_api_and_logs(self):
        C.m4_save("mock", {"username": fake_m4.USER, "password": fake_m4.PASSWORD})
        m = C.m4_masked()["profiles"]["mock"]; self.assertEqual(m["appKey"], M4.MASK); self.assertEqual(m["password"], M4.MASK)
        self.assertNotIn(fake_m4.APP_KEY, json.dumps(C.masked_settings()))
        C.m4_save("mock", {"appKey": M4.MASK}); self.assertEqual(C.m4_profile()["appKey"], fake_m4.APP_KEY)  # mask keeps stored value
        lg = M4.M4Adapter(self.url, C.log, {"username": fake_m4.USER, "password": fake_m4.PASSWORD, "auth": "login"}); lg.ping()
        self.draft("m4-log1"); C.submit_record(C.S["orders"]["m4-log1"])
        with open(C.P["log"], encoding="utf-8") as f: txt = f.read()
        self.assertNotIn(fake_m4.APP_KEY, txt); self.assertNotIn(fake_m4.PASSWORD, txt); self.assertIn("sign-in", txt)

    def test_status_mapping_and_defensive_parsing(self):
        f = M4.map_order_state
        self.assertEqual(f({"status": "Done"}), "FINISHED"); self.assertEqual(f({"status": "Cancelled"}), "STOPPED")
        self.assertEqual(f({"status": "Done", "fault": True}), "FINISHED")
        self.assertEqual(f({"status": "Executing", "fault": "true"}), "FAILED")
        self.assertEqual(f({"status": "Pending", "stepFixed": False}), "WAITING"); self.assertEqual(f({"status": "Pending", "stepFixed": True}), "RUNNING")
        self.assertEqual(f({"status": "Withdrawing"}), "WITHDRAWING"); self.assertEqual(f({"status": "Brandnew"}), "BRANDNEW")
        for s in ("Cancelling", "Withdrawing", "Brandnew", "ToBeAllocated", "Allocated", "Pending"):
            self.assertNotIn(f({"status": s}), C.INC_STOP); self.assertNotIn(f({"status": s}), C.AD().terminal_states)
        self.assertEqual(M4.as_obj('{"binTask": "Load"}'), {"binTask": "Load"}); self.assertEqual(M4.as_obj("not json"), {})
        self.assertEqual(M4.as_int("3"), 3); self.assertIsNone(M4.as_int("x"))
        self.draft("m4-st1"); ok, err = C.submit_record(C.S["orders"]["m4-st1"]); self.assertTrue(ok, err)
        js = C.AD().order_status("m4-st1")
        self.assertEqual(js["blockIds"], [s["id"] for s in C.S["orders"]["m4-st1"]["body"]["steps"]])
        self.assertEqual(C.AD().order_status("nope")["missing"], True)

    def test_scene_parsing_tolerant(self):
        st, js, _ = C.AD().scene(); self.assertEqual(st, 200)
        s = {x["name"]: x for x in C.AD().parse_stations(js)}
        self.assertEqual(len(s), 24); self.assertNotIn("AP99", s)  # LM+AP; disabled area skipped
        self.assertIn("LM3", s); self.assertEqual(s["LM3"]["pre"], "")  # LMs are selectable map stations
        self.assertEqual(s["AP3"]["pre"], "LM3"); self.assertEqual(s["AP3"]["bins"], ["BIN-3"]); self.assertIn("dir", s["AP1"])
        self.assertEqual(C.AD().parse_groups(js), [{"name": "grpA", "robots": ["AMB-01", "AMB-02"]}])
        curves, pts = C.AD().extract_geom(js)
        self.assertEqual(len(curves), 12)
        self.assertEqual(len(pts), 200)  # normalPosList, not station dots
        # Bezier / DegenerateBezier paths tessellate to >2 vertices; Straight stay 2-point
        by_n = {c["n"]: c for c in curves}
        self.assertGreater(len(by_n["LM1-AP1"]["p"]), 2, by_n["LM1-AP1"])
        self.assertGreater(len(by_n["LM3-AP3"]["p"]), 2, by_n["LM3-AP3"])
        self.assertEqual(len(by_n["LM5-AP5"]["p"]), 2)
        self.assertIn("Bezier", by_n["LM1-AP1"]["c"])
        weird = {"structure": {"areas": [{"mergedMap": {"points": [{"instanceName": "AP1", "pos": {"x": "1", "y": 2}}, {"id": "LM1", "x": 0, "y": 0}, "junk", 5],
                                                         "paths": [{"from": {"name": "LM1"}, "to": "AP1"}, {}], "bins": [{"id": "B", "point": "AP1"}, None]}}, "bad"]}}
        w = {x["name"]: x for x in C.AD().parse_stations(weird)}
        self.assertEqual(w["AP1"]["pre"], "LM1"); self.assertEqual(w["AP1"]["bins"], ["B"]); self.assertIn("LM1", w)
        self.assertEqual(C.AD().parse_stations({}), []); self.assertEqual(C.AD().parse_groups({"structure": None}), [])
        stations, err = C.load_scene_stations(); self.assertEqual(err, ""); self.assertEqual(C.S["prepoints"]["AP5"], "LM5")

    def test_m4_geom_via_build_geom(self):
        """Scene load yields non-empty downsampled point cloud + typed curves without manual smap."""
        g = C.build_geom(refresh=True)
        self.assertTrue(g.get("ok"), g); self.assertEqual(g.get("sceneErr"), "")
        self.assertGreater(g["npoints"], 0); self.assertEqual(len(g["curves"]), 12)
        self.assertIn("normalPosList", g.get("pointSrc") or "")
        self.assertTrue(any(len(c["p"]) > 2 for c in g["curves"]))

    def test_m4_pointcloud_via_map_download(self):
        """When schema has no normalPosList, download_maps (/scenes/{id}/download/{mapFile}) supplies the cloud."""
        import io, zipfile
        self.addCleanup(setattr, fake_m4, "SCHEMA_CLOUD", True)
        self.addCleanup(setattr, fake_m4, "DOWNLOAD_MAP", b"")
        fake_m4.SCHEMA_CLOUD = False
        cloud = [{"x": (i % 10) * 0.5, "y": (i // 10) * 0.5} for i in range(400)]
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w") as z:
            z.writestr("0.smap", json.dumps({"normalPosList": cloud, "advancedPointList": [], "advancedCurveList": []}))
        fake_m4.DOWNLOAD_MAP = bio.getvalue()
        # schema without cloud -> extract_geom empty points, then map download
        st, js, _ = C.AD().scene(); self.assertEqual(st, 200)
        _, pts0 = C.AD().extract_geom(js); self.assertEqual(pts0, [])
        code, raw = C.AD().download_maps(); self.assertEqual(code, 200); self.assertEqual(raw[:2], b"PK")
        g = C.build_geom(refresh=True)
        self.assertTrue(g.get("ok"), g); self.assertEqual(g.get("sceneErr"), "")
        self.assertGreater(g["npoints"], 0, g.get("notes"))
        self.assertIn("downloadScene", g.get("pointSrc") or "")
        self.assertEqual(len(g["curves"]), 12)  # routes still from schema

    def test_robots_and_poll_done(self):
        rl = C.AD().robots(); self.assertEqual({r["name"] for r in rl}, {"AMB-01", "AMB-02"})
        self.assertFalse([r for r in rl if r["name"] == "AMB-02"][0]["dispatchable"])
        self.draft("m4-full1"); C.S["running"] = True; C.send_batch(["m4-full1"], 0, 0)
        o = C.S["orders"]["m4-full1"]; self.assertEqual(o["state"], "SENT")
        self.assertTrue(self.run_until(lambda: o["state"] == "FINISHED", also=C.poll_once)); self.assertTrue(o.get("ended"))

    def test_cancel(self):
        self.draft("m4-c1"); C.submit_record(C.S["orders"]["m4-c1"]); C.AD().cancel("m4-c1")
        time.sleep(0.1); self.assertEqual(C.AD().order_status("m4-c1")["m4Status"], "Cancelling")
        self.assertNotIn(C.AD().order_status("m4-c1")["state"], C.TERMINAL())
        time.sleep(fake_m4.CANCEL_DUR); self.assertEqual(C.AD().order_status("m4-c1")["state"], "STOPPED")

class IncM4Test(Base):
    def test_block_by_block_until_done(self):
        ids = ["m4-inc%d" % i for i in range(2)]
        for i, oid in enumerate(ids): self.draft(oid, "AP%d" % (i + 1), "AP%d" % (i + 5))
        C.S["running"] = True; C.send_batch(ids, 0, 0, None, inc=True)
        for oid in ids:
            sent = [r for r in fake_m4.RECEIVED if r["id"] == oid][0]
            self.assertIs(sent["stepFixed"], False); self.assertEqual(len(sent["steps"]), 1)
        self.assertTrue(self.run_until(lambda: all(C.S["orders"][i]["inc"]["status"] == "done" for i in ids)))
        n = len(self.t["steps"])
        for oid in ids:
            ev = [e for e in fake_m4.EVENTS if e["id"] == oid]
            self.assertEqual([e["path"] for e in ev], ["add-steps"] * (n - 1) + ["complete-order"])
            self.assertTrue(all(e["prevState"] == "Done" for e in ev[:-1]), ev)
            self.assertEqual([s["id"] for s in fake_m4.ORDERS[oid]["steps"]], [s["id"] for s in C.S["orders"][oid]["body"]["steps"]])
        time.sleep(fake_m4.STEP_DUR + 0.1); self.assertEqual(C.AD().order_status(ids[0])["m4Status"], "Done")

    def test_fault_pauses_then_recovers(self):
        self.draft("m4-fault1"); C.S["running"] = True; C.send_batch(["m4-fault1"], 0, 0, None, inc=True)
        o = C.S["orders"]["m4-fault1"]; seen = []; faults = []
        def chk():
            if o["inc"].get("warn"): seen.append(o["inc"]["warn"])
            js = C.AD().order_status("m4-fault1")
            if js and js["fault"]: faults.append(js["state"])
        self.assertTrue(self.run_until(lambda: o["inc"]["status"] == "done", also=chk))
        self.assertTrue(faults and set(faults) == {"FAILED"}, faults)
        self.assertTrue(any("FAILED" in w for w in seen), seen); self.assertNotIn("warn", o["inc"])
        self.assertEqual(o["inc"]["sent"], len(self.t["steps"]))

    def test_query_errors_only_pause(self):
        self.draft("m4-qerr1"); C.S["running"] = True; C.send_batch(["m4-qerr1"], 0, 0, None, inc=True)
        o = C.S["orders"]["m4-qerr1"]
        self.assertTrue(self.run_until(lambda: o["inc"]["status"] == "done")); self.assertEqual(o["inc"]["sent"], len(self.t["steps"]))

    def test_append_errors_only_pause(self):
        self.draft("m4-aerr1"); C.S["running"] = True; C.send_batch(["m4-aerr1"], 0, 0, None, inc=True)
        o = C.S["orders"]["m4-aerr1"]; real = C.AD().add_blocks; calls = []
        def flaky(oid, blocks, complete=False):
            calls.append(1)
            return (False, "HTTP 400 mock") if len(calls) <= 3 else real(oid, blocks, complete)
        C.AD().add_blocks = flaky
        self.assertTrue(self.run_until(lambda: o["inc"]["status"] == "done")); self.assertGreater(len(calls), 3)

    def test_cancelled_in_m4_stops_appending(self):
        self.draft("m4-xcancel1"); C.S["running"] = True; C.send_batch(["m4-xcancel1"], 0, 0, None, inc=True)
        o = C.S["orders"]["m4-xcancel1"]
        self.assertTrue(self.run_until(lambda: o["inc"]["status"] == "stopped"))
        self.assertEqual(o["inc"]["reason"], "order STOPPED")
        n_ev = len(fake_m4.EVENTS); time.sleep(0.5); C.inc_once(); C.inc_once()
        self.assertEqual(len(fake_m4.EVENTS), n_ev)  # nothing appended after Cancelled

    def test_user_cancel_stops(self):
        self.draft("m4-uc1"); C.S["running"] = True; C.send_batch(["m4-uc1"], 0, 0, None, inc=True)
        o = C.S["orders"]["m4-uc1"]; C.AD().cancel("m4-uc1")
        self.assertTrue(self.run_until(lambda: o["inc"]["status"] == "stopped"))
        # Cancelling must not have stopped it early: the stop reason is the terminal Cancelled state
        self.assertEqual(o["inc"]["reason"], "order STOPPED")

    def test_done_stops(self):
        self.draft("m4-d1"); C.S["running"] = True; C.send_batch(["m4-d1"], 0, 0, None, inc=True)
        o = C.S["orders"]["m4-d1"]
        self.assertTrue(self.run_until(lambda: o["inc"]["status"] == "done")); n = len(fake_m4.EVENTS)
        time.sleep(0.5); C.inc_once(); self.assertEqual(len(fake_m4.EVENTS), n)

if __name__ == "__main__": unittest.main()
