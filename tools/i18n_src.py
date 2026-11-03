# -*- coding: utf-8 -*-
# =============================================================================
# WARNING - OUTDATED, DO NOT RUN.
# This file is NO LONGER the source of truth. It differs from the committed
# order_tester/i18n/zh.json and order_tester/i18n/en.json (those were edited
# directly): e.g. it has "st.pick" = "Add to pool" while the JSON has "Pools",
# and it lacks keys the JSON has (st.emptySel, st.selOnly, ord.gone, ord.goneTip).
# Running it OVERWRITES the current UI strings in zh.json/en.json with these
# stale ones. Edit the JSON files directly. (Running now requires --force.)
# =============================================================================
"""OUTDATED - do not run. Formerly the source of order_tester/i18n/{zh,en}.json.

The JSON files have since been edited directly and now differ from this file;
running it overwrites the current UI strings with stale ones. Edit
order_tester/i18n/{zh,en}.json instead. The script refuses to run without --force.
"""
import json, os, sys
D = {
 "app.title": ("订单派发测试工具", "Order Dispatch Tester"),
 "tab.cfg": ("配置与派单", "Config & Dispatch"), "tab.map": ("地图", "Map"), "tab.rob": ("机器人", "Robots"), "tab.ord": ("测试订单", "Test Orders"),
 "cfg.legend": ("配置", "Config"), "cfg.base": ("调度系统地址", "Dispatcher URL"), "cfg.poll": ("轮询间隔(秒)", "Poll interval (s)"),
 "cfg.stuck": ("卡死阈值(秒)", "Stuck threshold (s)"), "cfg.still": ("车辆静止阈值(秒)", "Vehicle idle threshold (s)"), "cfg.adapter": ("调度适配器", "Dispatcher adapter"),
 "sub.conn": ("连接", "Connection"), "sub.pool": ("站点池", "Pools"), "sub.tpl": ("订单模板", "Template"), "sub.gen": ("派单参数与生成", "Dispatch & Generate"),
 "cfg.lang": ("界面语言", "Language"), "sum.line": ("模板 {tpl} · {pools} · {strat} · 计划 {n} 单", "Template {tpl} · {pools} · {strat} · {n} orders planned"), "sum.noPool": ("(模板未使用站点池)", "(template uses no pool)"),
 "btn.save": ("保存", "Save"), "btn.use": ("使用", "Use"), "btn.add": ("添加", "Add"), "btn.clear": ("清空", "Clear"), "btn.del": ("删除", "Delete"),
 "btn.retry": ("重试", "Retry"), "btn.expandAll": ("全部展开", "Expand all"), "btn.collapseAll": ("全部折叠", "Collapse all"),
 "st.legend": ("站点", "Stations"), "st.load": ("从调度系统场景加载站点", "Load stations from scene"), "st.search": ("搜索", "Search"), "st.type": ("类型", "Type"),
 "st.paste": ("手动粘贴站点(逗号/换行分隔)", "Paste stations manually (comma/newline separated)"), "st.mapHint": ("(在\"地图\"页点击站点也可加入站点池)", "(you can also click stations on the Map tab)"),
 "st.name": ("站点", "Station"), "st.xy": ("坐标", "Position"), "st.pre": ("前置点", "Pre-point"), "st.pick": ("加入池", "Add to pool"),
 "pool.legend": ("站点池", "Station pools"), "pool.start": ("起点", "start"), "pool.end": ("终点", "end"), "pool.add": ("新建站点池", "New pool"),
 "pool.swap": ("互换", "Swap"), "pool.chipHint": ("点 × 删除单个点; 点芯片在地图上高亮该站点", "click × to remove a station; click a chip to highlight it on the map"),
 "pool.empty": ("(空)", "(empty)"), "pool.unused": ("(当前模板未使用)", "(not used by the template)"), "pool.del": ("删除池", "Delete pool"),
 "pool.rename": ("改名", "Rename"), "pool.renameQ": ("站点池 {p} 的新名称", "New name for pool {p}"), "pool.exists": ("站点池 {p} 已存在", "Pool {p} already exists"),
 "pool.delQ": ("删除站点池 {p}？", "Delete pool {p}?"), "pool.badName": ("池名只能用字母/数字/下划线, 且不能以数字开头", "Pool name: letters, digits, underscore; must not start with a digit"),
 "gen.strategy": ("生成策略", "Strategy"), "gen.random": ("随机 (不重复)", "Random (no reuse)"), "gen.rr": ("轮询 (round-robin)", "Round-robin"), "gen.cart": ("全组合 (笛卡尔积)", "Cartesian product"),
 "gen.noself": ("同一单内站点不重复 (排除起终点相同)", "No repeated station within an order"),
 "gen.noreuse": ("同一批内尽量不重复使用站点 (无放回抽样)", "Avoid reusing stations within a batch (sampling without replacement)"), "gen.noreuseShort": ("批内尽量不重复", "no reuse in batch"),
 "gen.line.random": ("每单从 {pools} 各随机取一个", "Each order picks one random station from {pools}"),
 "gen.line.round_robin": ("第 i 单取 {pools} 各池第 i 个 (循环)", "Order i takes the i-th station of {pools} (cycling)"),
 "gen.line.cartesian": ("{pools} 的所有组合各一单", "One order per combination of {pools}"),
 "gen.total": ("，共 {n} 单", ", {n} orders"), "gen.count": ("订单数 N", "Orders N"), "gen.countAuto": ("=默认", "=default"),
 "gen.countAutoTip": ("订单数跟随策略默认值 (随机=第一个池大小, 轮询=最大池, 全组合=组合数)", "Follow the strategy default (random = size of the first pool, round-robin = largest pool, cartesian = #combinations)"),
 "gen.btn": ("生成运单", "Generate orders"), "gen.hint": ("只生成, 不下发 — 到\"测试订单\"页勾选后下发", "Only generates drafts — send them from the Test Orders tab"),
 "gen.running": ("生成中...", "Generating..."), "gen.done": ("已生成 {n} 个待下发运单", "{n} draft orders generated"), "gen.skipped": ("跳过 {n}", "{n} skipped"), "gen.goSend": ("去下发 →", "Go send →"),
 "gen.poolEmpty": ("站点池为空: {p}", "Empty pool(s): {p}"), "gen.sameOnly": ("各池都只有同一个站点, 且勾选了站点不重复", "All pools contain only the same single station and 'no repeated station' is on"),
 "gen.missQ": ("以下站点无前置点, 不会为它们生成运单:\n{list}\n继续？", "These stations have no pre-point and will be skipped:\n{list}\nContinue?"),
 "tpl.legend": ("订单模板", "Order template"), "tpl.active": ("当前模板", "Template"), "tpl.new": ("新建", "New"), "tpl.copy": ("复制", "Copy"), "tpl.del": ("删除", "Delete"),
 "tpl.import": ("导入", "Import"), "tpl.export": ("导出", "Export"), "tpl.raw": ("JSON 编辑模式", "Raw JSON mode"), "tpl.title": ("说明", "Description"),
 "tpl.preview": ("示例订单预览 (调度系统 JSON)", "Sample order preview (dispatcher JSON)"), "tpl.prevInfo": ("示例取点: {p}", "Sample picks: {p}"),
 "tpl.unsaved": ("未保存...", "unsaved..."), "tpl.saved": ("已保存", "saved"), "tpl.saveErr": ("保存失败", "Save failed"),
 "tpl.namePrompt": ("模板名称 (字母/数字/_-.)", "Template name (letters/digits/_-.)"), "tpl.badName": ("模板名称不合法", "Invalid template name"),
 "tpl.overwriteQ": ("模板 {n} 已存在, 覆盖？", "Template {n} exists. Overwrite?"), "tpl.emptyHint": ("暂无模板 — 点「新建」为本服务器创建", "No templates yet — click New to create one for this server."),
 "tpl.lastOne": ("至少保留一个模板", "At least one template must remain"),
 "tpl.delQ": ("删除模板 {n}？(templates/{n}.json)", "Delete template {n}? (templates/{n}.json)"), "tpl.badJson": ("JSON 格式错误", "Invalid JSON"), "tpl.invalid": ("模板不合法", "Invalid template"),
 "step.on": ("启用", "On"), "step.id": ("ID", "ID"), "step.name": ("名称", "Name"), "step.loc": ("位置来源", "Location"), "step.op": ("动作 operation", "Operation"),
 "step.args": ("参数 args (JSON)", "Args (JSON)"), "step.add": ("+ 添加步骤", "+ Add step"), "step.vsOn": ("启用", "on"), "step.drag": ("拖动排序", "Drag to reorder"),
 "step.suffix": ("块后缀 ", "suffix "), "step.suffixTip": ("RDS blockId = 订单ID + 后缀 (默认 -ID)", "RDS blockId = order id + suffix (default -ID)"),
 "step.varHint": ("args 变量: {start} {end} {<池名>} {pickPre} {dropPre} {pre:<池名>} {stationOf:<步骤ID或stepN>} {preOf:<步骤>} {orderId}", "Args variables: {start} {end} {<pool>} {pickPre} {dropPre} {pre:<pool>} {stationOf:<step id or stepN>} {preOf:<step>} {orderId}"),
 "step.dupId": ("步骤 ID 为空或重复", "Step id empty or duplicated"), "step.argsObj": ("必须是 JSON 对象 {...}", "must be a JSON object {...}"),
 "step.lastOne": ("至少保留一个步骤", "At least one step is required"), "step.delQ": ("删除步骤 {n}？", "Delete step {n}?"),
 "step.defPick": ("取货", "Pick"), "step.defDrop": ("放货", "Drop"),
 "loc.pool": ("站点池", "Pool"), "loc.pre": ("另一步骤站点的前置点", "Pre-point of step"), "loc.fixed": ("固定站点", "Fixed station"),
 "vs.num": ("variableShape 的 head/tail 必须是数字", "variableShape head/tail must be numbers"),
 "disp.legend": ("派单参数", "Dispatch parameters"), "disp.group": ("机器人组", "Robot group"), "disp.groupTip": ("RDS setOrder 字段 group; 不指定=不带该字段", "RDS setOrder field 'group'; none = field omitted"),
 "disp.bbb": ("逐块下发", "Block-by-block"), "disp.bbbPoll": ("逐块轮询(秒)", "Block poll (s)"),
 "disp.bbbTip": ("勾选后: 下发时运单只带第一个块且 complete=false; 前一块 FINISHED 后用 /addBlocks 追加下一块, 最后一块追加后 /markComplete. 只要运单未到终态就不会停止追加: 运单/块 FAILED、Error、SUSPENDED、查询失败等只告警暂停并继续轮询, 恢复后继续追加; 仅运单终态 FINISHED/STOPPED(含在工具里取消)才停止. 对之后点击「下发」/自动派单生效", "When on: orders are sent with only the first block (complete=false); the next block is appended via /addBlocks once the previous one is FINISHED, then /markComplete after the last. Appending never stops while the order is not terminal: order/block FAILED, Error, SUSPENDED or query errors only pause (warning) and keep polling, appending resumes on recovery. Stops only when the order is FINISHED/STOPPED (incl. cancel in this tool). Applies to subsequent sends"),
 "inc.tag": ("逐块", "blocks"), "inc.appending": ("逐块下发中", "appending blocks"), "inc.done": ("已全部追加并封口(markComplete)", "all blocks appended, marked complete"),
 "inc.stopped": ("运单终态(FINISHED/STOPPED), 已停止追加", "order terminal (FINISHED/STOPPED), appending stopped"), "inc.waiting": ("运单/块异常, 已暂停等待恢复(继续轮询)", "order/block abnormal, paused until recovery (still polling)"), "inc.resumed": ("工具重启后已恢复跟踪", "resumed after tool restart"), "inc.pending": ("逐块下发进行中 {n} 单", "{n} block-by-block orders open"),
 "disp.none": ("不指定", "Any"), "disp.veh": ("指定车辆", "Vehicle"), "disp.vehPh": ("留空=自动分配", "empty = auto"), "disp.pri": ("优先级", "Priority"), "disp.label": ("label(可选)", "label (optional)"),
 "disp.preov": ("前置点手动映射(每行 站点=前置点, 优先于场景推导)", "Manual pre-point map (one 'station=pre-point' per line, overrides scene derivation)"),
 "pre.of": ("前置点", "Pre-point"), "pre.none": ("无", "none"), "pre.loading": ("场景加载中, 前置点稍后显示...", "Loading scene, pre-points will follow..."), "pre.manual": ("手动映射", "manual"),
 "pre.missNeeded": ("无前置点, 这些站点不会生成 (模板需要其前置点)", "No pre-point; these stations will be skipped (template needs their pre-point)"),
 "pre.missUnneeded": ("无前置点 (当前模板不需要, 不影响生成)", "No pre-point (not needed by this template)"),
 "map.layers": ("图层:", "Layers:"), "map.pc": ("点云", "Point cloud"), "map.rt": ("路线", "Routes"), "map.st": ("站点", "Stations"), "map.rb": ("车辆", "Vehicles"),
 "map.fit": ("适应视图", "Fit"), "map.needScene": ("尚未加载场景：请到「配置与派单 → 站点池」点「从调度系统场景加载站点」", "Scene not loaded: go to Config & Dispatch → Pools and click \"Load stations from dispatcher scene\""), "map.click": ("选择：", "Select:"), "map.pickFor": ("选{p}", "{p}"),
 "map.geomFail": ("几何加载失败", "Geometry load failed"),
 "map.geomInfo": ("路线 {c} 条{cs} · 点云 {p} 点{ps}", "{c} routes{cs} · {p} points{ps}"),
 "map.veh": ("车辆", "Vehicles"), "map.stillWithOrder": ("静止带单", "idle with order"), "map.orders": ("订单", "Orders"),
 "lg.multi": ("同时在多个池", "In several pools"), "lg.preOf": ("{p} 的前置点", "pre-point of {p}"), "lg.otherAP": ("其他 AP", "Other AP"), "lg.other": ("其他站点", "Other station"),
 "rob.legend": ("机器人", "Robots"), "rob.name": ("机器人", "Robot"), "rob.xy": ("坐标", "Position"), "rob.station": ("当前站点", "Station"), "rob.order": ("当前运单", "Order"),
 "rob.ostate": ("运单状态", "Order state"), "rob.disp": ("可调度", "Dispatchable"), "rob.conn": ("连接", "Connected"), "rob.blocked": ("阻挡", "Blocked"), "rob.batt": ("电量", "Battery"),
 "rob.idle": ("静止时长", "Idle"), "rob.sum": ("共 {n} · 有运单 {o}", "{n} total · {o} with order"), "rob.offline": ("离线/未上报", "offline / not reported"), "rob.ungrouped": ("未分组", "Ungrouped"),
 "rob.noOrder": ("无运单", "no order"), "rob.prev": ("上一单", "last"), "rob.deadlock": ("疑似死锁", "possible deadlock"),
 "ord.drafts": ("待下发", "Drafts"), "ord.selAll": ("全选待下发", "Select all drafts"), "ord.selNone": ("全不选", "Select none"), "ord.send": ("下发选中", "Send selected"),
 "ord.iv": ("本批间隔(秒)", "Interval (s)"), "ord.maxa": ("最大未完成订单", "Max open orders"), "ord.zeroUnl": ("(0=不限)", "(0 = unlimited)"), "ord.stop": ("停止下发", "Stop sending"),
 "ord.del": ("删除选中待下发", "Delete selected drafts"), "ord.swap": ("⇄ 互换选中待下发的起终点", "⇄ Swap start/end of selected drafts"),
 "ord.sent": ("已下发", "Sent"), "ord.cancelSel": ("取消选中订单", "Cancel selected"), "ord.cancelAll": ("取消全部未完成测试订单", "Cancel all open test orders"), "ord.clear": ("清空已下发列表", "Clear sent list"),
 "ord.clearQ": ("清空已下发订单列表 (待下发的保留)？", "Clear the sent-orders list (drafts are kept)?"), "ord.noDraftSel": ("没有勾选待下发的运单", "No draft selected"), "ord.noSentSel": ("未选择已下发的订单", "No sent order selected"),
 "ord.swapQ": ("互换 {n} 个待下发运单的起点/终点 (第一个池 ⇄ 最后一个池)？\n将按当前模板 {tpl} 重建 (前置点/变量/variableShape 等), 订单 ID 和机器人组不变。已下发的不受影响。", "Swap start/end (first ⇄ last pool) of {n} drafts?\nThey are rebuilt with the current template {tpl}; id and robot group are kept. Sent orders are not affected."),
 "ord.swapped": ("已互换 {n} 个", "{n} swapped"), "ord.notSwapped": ("未互换 {n} 个:", "{n} not swapped:"),
 "ord.sendQ": ("将向 {base} 下发 {n} 个真实订单\n间隔 {iv}s, 最大未完成 {ma}\n未勾选的保持待下发。确认？", "Send {n} real orders to {base}\ninterval {iv}s, max open {ma}\nUnselected drafts stay drafts. Confirm?"),
 "ord.ivShort": ("间隔", "interval"), "ord.unl": ("不限", "unlimited"), "ord.delQ": ("删除 {n} 个待下发运单 (不会影响调度系统)？", "Delete {n} drafts (the dispatcher is not affected)?"),
 "ord.cancelAllQ": ("取消全部未完成测试订单 (terminate)？", "Cancel all open test orders (terminate)?"), "ord.cancelQ": ("取消选中 {n} 个订单？", "Cancel {n} selected orders?"),
 "ord.none": ("(无)", "(none)"), "ord.nStuck": ("疑似卡死订单 {n}", "{n} possibly stuck"), "ord.active": ("进行中", "active "), "ord.selInfo": ("待下发 {n} · 已勾选 {s}", "{n} drafts · {s} selected"),
 "ord.nobatch": ("未分组", "No batch"), "ord.batch": ("批次", "Batch"), "ord.histBatch": ("历史批次", "Legacy batch"), "ord.sentAt": ("下发", "sent"), "ord.nOrders": ("{n} 单", "{n} orders"),
 "ord.stuckN": ("卡死 {n}", "{n} stuck"), "ord.total": ("总时长", "total"), "ord.inprog": ("进行中", "in progress"), "ord.grp": ("组", "group"),
 "ord.histLog": ("据日志", "from log"), "ord.histGap": ("按时间推断", "inferred by time"),
 "ord.histLogTip": ("改版前下发的订单, 按日志里的下发记录推断", "Sent before batches existed; grouped from the send log"), "ord.histGapTip": ("改版前下发的订单, 按下发时间间隔推断", "Sent before batches existed; grouped by send-time gaps"),
 "ord.selGrp": ("全选本组 (筛选后的)", "Select this group (filtered)"), "ord.failedTip": ("FAILED 不是终态, 仍在监控", "FAILED is not terminal; still monitored"),
 "ord.genAgo": ("生成于 {t}前", "generated {t} ago"), "ord.noVehTip": ("未分配车辆, 不计无变化", "No vehicle assigned yet; idle not counted"), "ord.backfillTip": ("来自调度系统订单详情 (补录)", "Backfilled from dispatcher order details"),
 "ord.hide": ("收起", "Hide"), "ord.view": ("查看", "View"),
 "col.id": ("订单ID", "Order ID"), "col.pair": ("站点 (起点→终点)", "Stations (start→end)"), "col.vs": ("车体形状", "variableShape"), "col.veh": ("车辆", "Vehicle"), "col.state": ("状态", "State"),
 "col.blocks": ("块状态", "Blocks"), "col.created": ("创建时间", "Created"), "col.age": ("已运行", "Age"), "col.idle": ("无变化", "Unchanged"), "col.started": ("开始执行时间", "Started"),
 "col.ended": ("结束时间", "Ended"), "col.dur": ("执行时长", "Duration"), "col.err": ("错误", "Error"), "col.json": ("JSON", "JSON"),
 "f.legend": ("筛选", "Filter"), "f.state": ("状态:", "State:"), "f.noneAll": ("(都不勾=全部)", "(none checked = all)"), "f.veh": ("车辆", "Vehicle"), "f.contains": ("含...", "contains..."), "f.all": ("全部", "All"),
 "f.pair": ("站点", "Stations"), "f.pairPh": ("匹配 起点→终点", "matches start → end"), "f.id": ("订单ID", "Order ID"), "f.stuck": ("只看疑似卡死", "Stuck only"), "f.hide": ("隐藏已结束", "Hide finished"),
 "f.clear": ("清除筛选", "Clear filter"), "f.match": ("匹配 {n}/{t}", "{n}/{t} match"),
 "state.draft": ("待下发", "Draft"), "state.other": ("其它", "Other"),
 "run.on": ("运行中", "Running"), "run.off": ("已停止", "Idle"), "run.sent": ("已发送", "sent"), "run.log": ("日志", "log"),
 "msg.loading": ("加载中...", "Loading..."), "msg.loaded": ("已加载保存的设置", "Saved settings loaded"), "msg.fromLocal": ("已从浏览器缓存恢复设置", "Settings restored from browser cache"),
 "msg.loadedScene": ("已加载保存的设置 · 场景站点 {n}", "Settings loaded · {n} scene stations"), "msg.nStations": ("站点数 {n}", "{n} stations"),
 "msg.sceneLoading": ("加载场景站点 (/scene 可能需要 30-60 秒)...", "Loading scene stations (/scene can take 30-60 s)..."), "msg.sceneFail": ("场景加载失败", "Scene load failed"), "scene.loadedAt": ("场景加载于 {t}", "Scene loaded at {t}"), "prog.request": ("请求 /scene，等待调度系统响应…", "Requesting /scene, waiting for the dispatcher…"), "prog.download": ("下载场景", "Downloading scene"), "prog.parse": ("解析站点/路线", "Parsing stations / routes"), "prog.pointcloud": ("解析点云", "Parsing point cloud"), "prog.mapdl": ("下载地图 (/downloadScene)", "Downloading map (/downloadScene)"), "prog.mapparse": ("解压/解析地图", "Unpacking / parsing map"), "prog.downsample": ("降采样点云", "Downsampling point cloud"), "prog.mapcache": ("地图未变, 复用点云缓存", "Map unchanged, reusing point cloud cache"), "prog.points": ("点", "points"), "map.dir": ("站点朝向", "Station heading"), "map.angle": ("角度", "angle"), "map.ignoreDir": ("ignoreDir: 不限朝向", "ignoreDir: any heading"), "map.pcThin": ("细", "thin"), "map.pcMed": ("中", "medium"), "map.pcBold": ("粗", "bold"), "map.pcXBold": ("特粗", "extra bold"), "map.pcSizeTip": ("点云点大小 (屏幕像素, 缩放时不变)", "Point size in screen pixels (stays the same when zooming)"), "prog.cache": ("写入缓存", "Writing cache"), "prog.done": ("完成", "Done"), "prog.failed": ("失败", "Failed"), "prog.elapsed": ("已用 {s} 秒", "{s} s elapsed"), "sel.nearest": ("最近(默认)", "nearest (default)"), "sel.index": ("按序号", "by number"), "sel.name": ("按名称/通配符", "by name / wildcard"), "sel.dir": ("按方向", "by direction"), "sel.random": ("每单随机", "random per order"), "sel.tip": ("多个候选前置点时选哪一个；候选顺序见站点表", "Which candidate pre-point to use when there are several; candidate order is shown in the station table"), "sel.binTip": ("该站有多个库位时选哪一个；选项与前置点相同（最近、按序号、按名称/通配符、按方向、每单随机）。候选是该站的库位列表，按列表顺序。", "Which bin to use when the station has several; same choices as a pre-point (nearest, by number, by name / wildcard, by direction, random per order). Candidates are that station's bins, in list order."), "tgt.station": ("走点位", "Station"), "tgt.bin": ("走库位", "Bin"), "tgt.tip": ("先确定站点，再选择走该点位还是走该站的库位。多个库位时用与前置点相同的选择标准，不点名具体库位。", "After the station is resolved, go to that station or to a bin on it. Several bins use the same selection as pre-points, not a list of bin names."), "tgt.noBin": ("该站没有库位，生成时回退走点位", "No bin on this station; generation falls back to the station"), "tgt.oneBin": ("只有一个库位，直接使用", "Only one bin; it is used directly"), "pre.dir.in": ("驶入", "in"), "pre.dir.out": ("驶出", "out"), "pre.dir.prop": ("属性", "property"), "pre.notLm": ("非LM", "not LM"), "pre.manualList": ("手动", "manual"), "busy.scene": ("正在加载场景… (/scene 可能需要 30-60 秒)", "Loading scene… (/scene can take 30-60 s)"),
 "msg.pasted": ("粘贴 {n} 个", "{n} pasted"), "msg.noSceneCoords": ("(场景未加载, 无法解析坐标/前置点)", "(scene not loaded: no positions / pre-points)"), "msg.notInScene": ("场景中未找到", "not in scene"),
 # server side
 "srv.noPoolStep": ("模板中没有使用站点池的步骤", "The template has no pool-based step"), "srv.poolEmpty": ("站点池为空: {pools}", "Empty pool(s): {pools}"),
 "srv.sameOnly": ("各池都只有同一个站点, 且勾选了站点不重复", "All pools contain only the same single station and 'no repeated station' is on"),
 "srv.sceneFail": ("无法加载场景以推导前置点: {err}", "Cannot load the scene to derive pre-points: {err}"),
 "srv.preLineBad": ("前置点手动映射第 {n} 行写法不对: {line}（应为 站点=前置点 或 站点=前置点1|前置点2）", "Pre-point map line {n} is invalid: {line} (use STATION=PRE or STATION=PRE1|PRE2)"), "srv.preLineDup": ("前置点手动映射第 {n} 行: 站点 {st} 重复", "Pre-point map line {n}: station {st} appears twice"), "srv.noPre": ("池 {pool} 中以下站点无前置点, 不会生成: {list}", "Pool {pool}: no pre-point, skipped: {list}"), "srv.poolNowEmpty": ("(池 {pool} 已空, 请在前置点映射中手动指定)", "(pool {pool} is now empty; add a manual pre-point mapping)"),
 "srv.noPickPreHint": ("提示: 以下起点无取货前置点 (当前模板不需要): {list}", "Note: these start stations have no pre-point (not needed by this template): {list}"),
 "srv.notDraft": ("不是待下发", "not a draft"), "srv.inBatch": ("在正在下发的批次中", "in the batch being sent"), "srv.changed": ("状态已变化", "state changed"),
 "srv.sendEnd": ("下发结束: 已下发 {n}", "Send finished: {n} sent"), "srv.sendLeft": (", 未下发 {n} (仍为待下发)", ", {n} not sent (still drafts)"), "srv.autoEnd": ("派单结束", "Auto dispatch finished"),
 "srv.running": ("正在下发中, 请先停止或等待完成", "Already sending; stop or wait first"), "srv.noDraftSel": ("没有选中待下发的运单", "No draft selected"),
 "srv.badSmap": ("无法解析: 不是 JSON .smap, 也不是含 .smap 的 zip 包", "Cannot parse: neither a JSON .smap nor a zip containing .smap"), "srv.noFile": ("文件不存在: {path}", "File not found: {path}"),
 "srv.tplExists": ("模板 {name} 已存在", "Template {name} exists"),
}
if __name__ == "__main__":
    if "--force" not in sys.argv[1:]:
        sys.exit("tools/i18n_src.py is OUTDATED and differs from order_tester/i18n/{zh,en}.json; "
                 "running it would overwrite the current UI strings. Edit the JSON files directly, "
                 "or pass --force if you really mean it.")
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "order_tester", "i18n")
    os.makedirs(out, exist_ok=True)
    for i, lang in enumerate(("zh", "en")):
        with open(os.path.join(out, lang + ".json"), "w", encoding="utf-8") as f:
            json.dump({k: v[i] for k, v in sorted(D.items())}, f, ensure_ascii=False, indent=1); f.write("\n")
    print("wrote", len(D), "keys")
