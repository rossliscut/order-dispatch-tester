# -*- coding: utf-8 -*-
"""Pool entries may be a station string or {station, bin?}. Strings stay strings.
M4 step location is the bin name; pre-points and noSelf use the station. RDS location stays the station."""
import json, random, unittest
from helpers import C, fresh_core, PREPOINTS
from order_tester import templates as T

def bin_tpl():
    return {"name": "binloc", "steps": [
        {"id": "s", "name": "pick", "enabled": True, "location": {"type": "pool", "pool": "start"},
         "operation": "ForkLoad", "opMode": "binTask", "args": {"loc": "{start}"}},
        {"id": "w", "name": "pre", "enabled": True, "location": {"type": "pre", "step": "e"},
         "operation": "Wait", "opMode": "operation", "args": {}},
        {"id": "e", "name": "drop", "enabled": True, "location": {"type": "pool", "pool": "end"},
         "operation": "ForkUnload", "opMode": "operation",
         "args": {"st": "{stationOf:e}", "pre": "{pre:end}", "loc": "{end}", "of": "{preOf:s}"}},
        {"id": "f", "name": "fixed", "enabled": True,
         "location": {"type": "fixed", "station": " AP9 ", "bin": " Loc-9 "},
         "operation": "none", "opMode": "operation", "args": {}},
    ]}

class NormalizeTest(unittest.TestCase):
    def test_normalize_keeps_strings_and_bins(self):
        raw = ["AP1", " AP1 ", {"station": "AP1"}, {"station": "AP1", "bin": ""},
               {"station": "LM3953", "bin": " Loc-7-1 "}, {"station": "LM3953", "bin": "Loc-7-1"},
               {"bin": "x"}, None, 3, {"station": "  ", "bin": "Loc"}]
        self.assertEqual(T.normalize_pool_list(raw), ["AP1", {"station": "LM3953", "bin": "Loc-7-1"}])
        self.assertEqual(T.entry_label("AP1"), "AP1")
        self.assertEqual(T.entry_label({"station": "LM3953", "bin": "Loc-7-1"}), "LM3953 · Loc-7-1")
        self.assertEqual(T.entry_location({"station": "LM3953", "bin": "Loc-7-1"}), "Loc-7-1")
        self.assertEqual(T.entry_station({"station": "LM3953", "bin": "Loc-7-1"}), "LM3953")

    def test_save_and_migrate_roundtrip(self):
        fresh_core(self)
        C.save_settings({"pools": {"start": ["AP2", {"station": "AP2"}, {"station": "LM3953", "bin": "Loc-7-1"},
                                              {"station": "LM3953", "bin": "  "}], "end": ["AP9"]}})
        st = C.load_settings()
        # a whitespace bin is "no bin", so the station itself is kept beside the real bin entry
        self.assertEqual(st["pools"]["start"], ["AP2", {"station": "LM3953", "bin": "Loc-7-1"}, "LM3953"])
        self.assertEqual(st["pools"]["end"], ["AP9"])
        with open(C.P["settings"], encoding="utf-8") as f: raw = json.load(f)
        srv = raw["servers"][0]
        srv["pools"]["start"] = [{"station": "AP1", "bin": ""}, {"bin": "nope"}, {"station": "LM1", "bin": "Loc-1"}, "AP2", "AP2"]
        srv["pools"]["end"] = ["AP9"]
        with open(C.P["settings"], "w", encoding="utf-8") as f: json.dump(raw, f)
        notes = C.migrate_pool_entries()
        self.assertEqual(notes, ["pools normalized (station/bin entries)"])
        self.assertEqual(C.migrate_pool_entries(), [])  # idempotent
        self.assertEqual(C.load_settings()["pools"]["start"], ["AP1", {"station": "LM1", "bin": "Loc-1"}, "AP2"])
        # a later startup migrate does not touch an already-canonical pool
        notes = C.migrate_templates()
        self.assertFalse(any("normalized" in n or "migrated from starts" in n for n in notes))
        self.assertEqual(C.migrate_templates(), [])
        self.assertEqual(C.load_settings()["pools"]["start"], ["AP1", {"station": "LM1", "bin": "Loc-1"}, "AP2"])

class StrategyTest(unittest.TestCase):
    def test_noself_compares_station_not_bin(self):
        both = [("start", [{"station": "AP1", "bin": "B1"}, {"station": "AP1", "bin": "B2"}]), ("end", ["AP1"])]
        self.assertEqual(T.make_picker("cartesian", both).default_count(), 0)
        self.assertEqual(T.make_picker("cartesian", both, no_self=False).default_count(), 2)
        ok = [("start", [{"station": "AP1", "bin": "B1"}, "AP1"]), ("end", ["AP2"])]
        cp = T.make_picker("cartesian", ok)
        got = [cp.next() for _ in range(cp.default_count())]
        self.assertEqual(len(got), 2)
        self.assertTrue(all(T.entry_station(c["start"]) != c["end"] for c in got))
        rr = T.make_picker("round_robin", [("start", ["AP2", "AP1"]), ("end", [{"station": "AP1", "bin": "X"}, "AP3"])])
        self.assertEqual(rr.next(), {"start": "AP2", "end": {"station": "AP1", "bin": "X"}})
        self.assertEqual(rr.next(), {"start": "AP1", "end": "AP3"})
        rp = T.make_picker("random", [("start", [{"station": "S1", "bin": "A"}, {"station": "S2", "bin": "B"}]),
                                      ("end", ["S1", "S2"])], rng=random.Random(0), no_reuse=False)
        for _ in range(40):
            p = rp.next()
            self.assertNotEqual(T.entry_station(p["start"]), T.entry_station(p["end"]))

    def test_string_pools_round_robin_unchanged(self):
        pools = [("start", ["A", "B", "C"]), ("end", ["A", "B"])]
        rr = T.make_picker("round_robin", pools)
        self.assertEqual([rr.next() for _ in range(4)],
                         [{"start": "A", "end": "B"}, {"start": "B", "end": "A"}, {"start": "C", "end": "A"}, {"start": "A", "end": "B"}])

class GenerateTest(unittest.TestCase):
    def setUp(self):
        fresh_core(self)
        C.S["prepoints"] = dict(PREPOINTS)
        self.t = bin_tpl(); self.assertEqual(T.validate(self.t), [])
        self.assertEqual(self.t["steps"][3]["location"], {"type": "fixed", "station": "AP9", "bin": "Loc-9"})
        C.S["store"].put(self.t)

    def _pools(self):
        b = {"templateName": "binloc", "pools": {
            "start": [{"station": "AP1", "bin": " Loc-7-1 "}, "AP1"],
            "end": [{"station": "AP2", "bin": "Loc-7-2"}]},
             "strategy": "round_robin", "count": 1, "noSelf": True}
        cfg, t, pools, warn, err = C.prepare_cfg(b)
        self.assertEqual(err, ""); self.assertEqual(warn, "")
        self.assertEqual(pools["start"], [{"station": "AP1", "bin": "Loc-7-1"}, "AP1"])
        self.assertEqual(pools["end"], [{"station": "AP2", "bin": "Loc-7-2"}])
        return cfg, t, pools

    def test_same_station_rejected_when_noself(self):
        b = {"templateName": "binloc", "pools": {"start": [{"station": "AP1", "bin": "Loc-7-1"}], "end": ["AP1"]}, "noSelf": True}
        cfg, t, pools, warn, err = C.prepare_cfg(b)
        self.assertIn("同一个站点", err)

    def test_m4_location_is_bin_and_pre_uses_station(self):
        cfg, t, pools = self._pools()
        C.save_settings({"adapter": "m4"}); C.set_adapter("m4"); C.S["prepoints"] = dict(PREPOINTS)
        res = C.generate_drafts(cfg, t, pools, id_factory=lambda: "m4-bin")
        self.assertEqual(res["n"], 1); self.assertEqual(res["skipped"], [])
        rec = C.S["orders"]["m4-bin"]
        steps = {s["id"]: s for s in rec["body"]["steps"]}
        self.assertEqual(steps["m4-bin-s"]["location"], "Loc-7-1")
        self.assertEqual(steps["m4-bin-s"]["rbkArgs"], {"binTask": "ForkLoad"})  # action mode, no bin key
        self.assertEqual(steps["m4-bin-e"]["location"], "Loc-7-2")
        self.assertEqual(steps["m4-bin-e"]["rbkArgs"], {"operation": "ForkUnload", "st": "AP2", "pre": "LM2", "loc": "Loc-7-2", "of": "LM1"})
        self.assertEqual(steps["m4-bin-w"]["location"], "LM2")  # pre of AP2, not of Loc-7-2
        self.assertEqual(steps["m4-bin-f"]["location"], "Loc-9")
        self.assertEqual(rec["pair"], ["AP1 · Loc-7-1", "AP2 · Loc-7-2"])

    def test_rds_location_stays_station(self):
        cfg, t, pools = self._pools()
        self.assertEqual(C.AD().name, "rds")
        res = C.generate_drafts(cfg, t, pools, id_factory=lambda: "rds-bin")
        self.assertEqual(res["n"], 1)
        blocks = {b["blockId"]: b for b in C.S["orders"]["rds-bin"]["body"]["blocks"]}
        self.assertEqual(blocks["rds-bin-s"]["location"], "AP1")
        self.assertEqual(blocks["rds-bin-e"]["location"], "AP2")
        self.assertEqual(blocks["rds-bin-w"]["location"], "LM2")
        self.assertEqual(blocks["rds-bin-f"]["location"], "AP9")
        self.assertNotIn("operation_args", blocks["rds-bin-s"])  # binTask: action name only
        self.assertEqual(blocks["rds-bin-e"]["operation_args"], {"st": "AP2", "pre": "LM2", "loc": "AP2", "of": "LM1"})
        self.assertNotIn("Loc-", json.dumps(C.S["orders"]["rds-bin"]["body"]))

    def test_pool_step_bin_sets_m4_location(self):
        t = bin_tpl()
        t["steps"][0]["location"]["bin"] = "  Loc-7-1  "
        self.assertEqual(T.validate(t), [])
        self.assertEqual(t["steps"][0]["location"].get("bin"), "Loc-7-1")
        pre = lambda n: PREPOINTS.get(n, "")
        m4 = T.build_order(t, {"start": "AP1", "end": "AP2"}, {}, pre, "stepbin", bin_targets=True)
        by = {s["id"]: s for s in m4["steps"]}
        self.assertEqual(by["s"]["location"], "Loc-7-1")
        self.assertEqual(by["s"]["args"]["loc"], "Loc-7-1")  # {start} follows the step bin
        self.assertEqual(by["w"]["location"], "LM2")  # pre still uses the end station
        self.assertEqual(by["e"]["location"], "AP2")
        rds = T.build_order(t, {"start": "AP1", "end": "AP2"}, {}, pre, "rdsbin", bin_targets=False)
        self.assertEqual([s for s in rds["steps"] if s["id"] == "s"][0]["location"], "AP1")
        t["steps"][0]["location"]["bin"] = "   "
        T.validate(t)
        self.assertNotIn("bin", t["steps"][0]["location"])

    def test_string_only_pool_still_matches_station_location(self):
        b = {"templateName": "binloc", "pools": {"start": ["AP4", "AP5"], "end": ["AP6"]},
             "strategy": "round_robin", "count": 1, "noSelf": True}
        cfg, t, pools, warn, err = C.prepare_cfg(b)
        self.assertEqual(err, "")
        self.assertEqual(pools, {"start": ["AP4", "AP5"], "end": ["AP6"]})
        C.generate_drafts(cfg, t, pools, id_factory=lambda: "plain")
        blocks = {b["blockId"]: b for b in C.S["orders"]["plain"]["body"]["blocks"]}
        self.assertEqual(blocks["plain-s"]["location"], "AP4")
        self.assertEqual(blocks["plain-e"]["location"], "AP6")
        self.assertEqual(blocks["plain-w"]["location"], "LM6")
        self.assertEqual(C.S["orders"]["plain"]["pair"], ["AP4", "AP6"])

if __name__ == "__main__":
    unittest.main()
