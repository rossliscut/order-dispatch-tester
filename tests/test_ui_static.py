import json, os, re, unittest
D = os.path.join(os.path.dirname(__file__), "..", "order_tester")

class StationListReadOnlyTest(unittest.TestCase):
    def setUp(self):
        self.js = open(os.path.join(D, "static", "app.js"), encoding="utf-8").read()
    def body(self):
        i = self.js.index("function renderSt(")
        return self.js[i:self.js.index("let hlSt", i)]
    def test_no_add_buttons_and_lists_only_pooled(self):
        b = self.body()
        self.assertNotIn("pick(", b)          # per-row pool buttons removed
        self.assertIn("inSel", b)            # rows come from pool membership, not all scene stations
        self.assertNotIn("stations.filter(", b)
        self.assertIn("st.emptySel", b)
    def test_i18n_keys(self):
        for l in ("zh", "en"):
            d = json.load(open(os.path.join(D, "i18n", l + ".json"), encoding="utf-8"))
            for k in ("st.pick", "st.emptySel", "st.selOnly"): self.assertTrue(d.get(k), (l, k))

class InPageDialogTest(unittest.TestCase):
    def test_no_native_dialogs(self):
        # native confirm/prompt/alert are suppressed in some embedded browsers (buttons silently do nothing)
        js = open(os.path.join(D, "static", "app.js"), encoding="utf-8").read()
        for f in ("confirm", "prompt", "alert"):
            self.assertIsNone(re.search(r"(?<![\w.$])%s\(" % f, js), f)
        for f in ("function uiConfirm(", "function uiPrompt(", "function uiAlert(", "function uiDlg("): self.assertIn(f, js)
        for f in ("delDrafts", "swapDrafts", "sendSel"):
            i = js.index("async function %s()" % f); body = js[i:js.index("\nasync function", i + 1)] if "\nasync function" in js[i + 1:] else js[i:]
            self.assertIn("await uiConfirm(", body, f)
        self.assertIn(".uidlg{", open(os.path.join(D, "static", "index.html"), encoding="utf-8").read())
        for l in ("zh", "en"):
            d = json.load(open(os.path.join(D, "i18n", l + ".json"), encoding="utf-8"))
            for k in ("btn.ok", "btn.cancel"): self.assertTrue(d.get(k), (l, k))

class M4UiTest(unittest.TestCase):
    def test_keep_final_path_space_column(self):
        html = open(os.path.join(D, "static", "index.html"), encoding="utf-8").read()
        js = open(os.path.join(D, "static", "app.js"), encoding="utf-8").read()
        self.assertIn("<th class=m4-col", html); self.assertIn("#steps:not(.no-vs) .m4-col{display:none}", html)  # M4 only, mirror of vs-col
        self.assertIn("class=stkfs", js); self.assertIn("function setKfs(", js)
        for l in ("zh", "en"):
            d = json.load(open(os.path.join(D, "i18n", l + ".json"), encoding="utf-8"))
            for k in ("step.kfs", "step.kfsTip"): self.assertTrue(d.get(k), (l, k))

    def test_m4_fields_and_i18n(self):
        html = open(os.path.join(D, "static", "index.html"), encoding="utf-8").read()
        self.assertIn("id=m4appkey type=password", html); self.assertIn("id=m4pass type=password", html)
        self.assertIn("<option value=rds>RDS</option>", html)  # RDS first = default
        self.assertNotIn("id=langsel2", html)  # language only in top-right langsel
        self.assertNotIn("id=m4scene ", html); self.assertNotIn("id=m4scene>", html)  # scene dropdown only
        self.assertIn("id=m4scenes", html)
        self.assertNotIn("id=m4prof", html); self.assertNotIn("id=m4name", html)  # no multi-profile UI; connection per server
        self.assertNotIn("m4.profile", html); self.assertNotIn("m4.profileName", html)
        self.assertIn('value=appkey', html); self.assertIn('value=login', html)
        self.assertNotIn('m4.authAuto', html); self.assertNotIn('m4.authNone', html)
        self.assertIn('id=m4authKey', html); self.assertIn('id=m4authLogin', html)
        # Per-step action mode (binTask|operation); no global template/connection opMode switch
        self.assertNotIn('id=m4opWrap', html); self.assertNotIn('id=m4op', html)
        self.assertIn('data-i18n=step.mode', html)
        self.assertIn('data-i18n=step.action', html)
        self.assertNotIn('id=m4op', html[html.index('id=m4box'):html.index('data-sub=tpl')])
        # Template page: left list + right editor, no top dropdown; name editable; vs col marked
        self.assertIn('id=tpl_layout', html); self.assertIn('id=tpl_list', html); self.assertIn('id=tpl_side', html); self.assertIn('id=tpl_main', html)
        # Global per-server list (app-level left rail, all main tabs)
        self.assertIn('id=app_body', html); self.assertIn('id=app_main', html)
        self.assertIn('id=srv_side', html); self.assertIn('id=srv_list', html); self.assertIn('id=cfg_main', html)
        self.assertNotIn('id=cfg_layout', html)
        self.assertIn('id=srv_edge', html); self.assertNotIn('id=srv_toggle', html)  # topbar hide button removed; edge « only
        self.assertIn('id=app_brand', html)
        # App title sits in left server rail (not a full-width top bar)
        brand = html[html.index('id=app_brand'):html.index('id=srv_list')]
        self.assertIn('data-i18n=app.title', brand)
        self.assertLess(html.index('id=tabbar'), html.index('id=tab-cfg'))
        self.assertGreater(html.index('id=tabbar'), html.index('id=srv_side'))
        self.assertIn('onclick=addServer()', html); self.assertIn('favicon.svg', html); self.assertTrue(os.path.isfile(os.path.join(D, 'static', 'favicon.svg'))); self.assertIn('onclick=renameServer()', html); self.assertIn('onclick=delServer()', html)
        self.assertIn('onclick=toggleSrvSide()', html)
        js = open(os.path.join(D, "static", "app.js"), encoding="utf-8").read()
        self.assertIn('function selectServer', js)
        self.assertIn('function clearServerUi', js)
        self.assertIn('robotsCache=[]', js); self.assertIn('ordersCache=[]', js)
        self.assertIn("adapter:'rds'", js)  # new server always RDS
        self.assertNotIn('clearSceneUi', js)
        self.assertIn("t('srv.nameRequired')", js)
        self.assertIn('nameRequired', js)
        self.assertNotIn("$('base').value.trim()||'http://127.0.0.1:8088'", js)
        self.assertIn('function renderSrvList', js)
        self.assertIn('function toggleSrvSide', js)
        self.assertIn('odtSrvCollapsed', js)
        # srv_side is outside tab-cfg (global)
        self.assertLess(html.index('id=srv_side'), html.index('id=tab-cfg'))
        self.assertLess(html.index('id=srv_side'), html.index('id=tab-map'))

        self.assertIn('id=tpl_name', html); self.assertNotIn('id=tpl_sel', html)
        self.assertIn('vs-col', html); self.assertIn("no-vs", open(os.path.join(D, "static", "app.js"), encoding="utf-8").read())
        self.assertIn('function renameTpl', open(os.path.join(D, "static", "app.js"), encoding="utf-8").read())
        self.assertIn('function fillTplList', open(os.path.join(D, "static", "app.js"), encoding="utf-8").read())
        js = open(os.path.join(D, "static", "app.js"), encoding="utf-8").read()
        # ID column: single input; no blockSuffix editor / suffix i18n in the step row template
        rs = js[js.index("function renderSteps("):js.index("function setF(")]
        self.assertNotIn("blockSuffix", rs); self.assertNotIn("step.suffix", rs)

        js_all = open(os.path.join(D, "static", "app.js"), encoding="utf-8").read()
        self.assertIn('function m4OpUi', js_all)
        self.assertNotIn('function m4SaveOp', js_all)
        self.assertIn('function setOpMode', js_all); self.assertIn('function stepOpMode', js_all)
        rs = js_all[js_all.index("function renderSteps("):js_all.index("function setF(")]
        self.assertIn('setOpMode', rs); self.assertIn('stom', rs); self.assertIn('om-bin', rs)
        self.assertNotIn('id=m4base', html)
        self.assertIn('onclick=saveCfg()', html)
        self.assertNotIn('m4.btnSave', html)
        self.assertEqual(html.count('onclick=saveCfg()'), 1)
        self.assertLess(html.index('id=m4box'), html.index('onclick=saveCfg()'))  # save below m4box
        self.assertNotIn('onclick=m4Del()', html)
        self.assertNotIn('function m4Del', js_all)
        self.assertNotIn('m4prof', js_all); self.assertNotIn('m4name', js_all)
        self.assertIn('function m4ActiveName', js_all); self.assertIn('function m4Save', js_all)
        self.assertIn('m4SceneLabel', open(os.path.join(D, "static", "app.js"), encoding="utf-8").read())
        self.assertIn('（', open(os.path.join(D, "static", "app.js"), encoding="utf-8").read())
        self.assertNotIn('id=rdsBaseWrap', html)
        self.assertIn('id=base', html)
        self.assertIn('function adapterUi', open(os.path.join(D, "static", "app.js"), encoding="utf-8").read())
        self.assertIn('function persistDispatcherUrl', open(os.path.join(D, "static", "app.js"), encoding="utf-8").read())

        keys = set(re.findall(r"data-i18n(?:-ph)?=([\w.]+)", html))
        for l in ("zh", "en"):
            d = json.load(open(os.path.join(D, "i18n", l + ".json"), encoding="utf-8"))
            self.assertEqual([k for k in keys if not d.get(k)], [], l)
        zh = json.load(open(os.path.join(D, "i18n", "zh.json"), encoding="utf-8")); en = json.load(open(os.path.join(D, "i18n", "en.json"), encoding="utf-8"))
        self.assertEqual(set(zh), set(en))

class MapToolbarTest(unittest.TestCase):
    def test_no_manual_smap_upload_or_path(self):
        html = open(os.path.join(D, "static", "index.html"), encoding="utf-8").read()
        js = open(os.path.join(D, "static", "app.js"), encoding="utf-8").read()
        self.assertNotIn("id=smapf", html)
        self.assertNotIn("id=smap_path", html)
        self.assertNotIn("map.upload", html)
        self.assertNotIn("uploadSmap", js)
        self.assertNotIn("useSmapPath", js)
        # Station labels drawn whenever the stations layer is on (not zoom-gated)
        i = js.index("function drawStations(")
        body = js[i:js.index("function drawLegend(", i)]
        self.assertNotIn("view.s>15", body)

class VersionFooterTest(unittest.TestCase):
    def test_version_module_api_and_footer(self):
        from order_tester import version as V
        self.assertTrue(V.VERSION)
        self.assertRegex(V.BUILD_DATE, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC$")
        srv = open(os.path.join(D, "server.py"), encoding="utf-8").read()
        self.assertIn('/api/version', srv)
        self.assertIn("V.VERSION", srv)
        self.assertIn("V.BUILD_DATE", srv)
        html = open(os.path.join(D, "static", "index.html"), encoding="utf-8").read()
        self.assertIn("id=ver_footer", html)
        self.assertIn("#ver_footer", html)
        self.assertIn("pointer-events:none", html)
        js = open(os.path.join(D, "static", "app.js"), encoding="utf-8").read()
        self.assertIn("function loadVersion", js)
        self.assertIn("/api/version?_=", js)
        self.assertIn("await loadVersion()", js)

class OrdFiltDraftVisibilityTest(unittest.TestCase):
    """Group/vehicle filters must not hide drafts that have no assigned group/vehicle."""
    def test_match_skips_grp_veh_for_unassigned_drafts(self):
        js = open(os.path.join(D, "static", "app.js"), encoding="utf-8").read()
        i = js.index("const match=o=>{")
        body = js[i:js.index("let gm=new Map()", i)]
        self.assertIn("(o.state!=DRAFT||(o.vehicle||''))", body)
        self.assertIn("(o.state!=DRAFT||ogrp(o))", body)
        # bare pre-fix form must not remain
        self.assertNotIn("if(f.veh&&!(o.vehicle||'').toLowerCase()", body)
        self.assertNotIn("if(f.grp&&ogrp(o)!==f.grp)", body)

