# 项目说明

给人看的操作步骤在 [USAGE.zh.md](USAGE.zh.md) 与 [USAGE.en.md](USAGE.en.md)。给编码工具的硬性规矩在仓库根目录的 [AGENTS.md](../AGENTS.md)。这里只讲背景、结构和已经定下来的设计。不确定的标「待补」。

## 背景与目标

订单派发测试工具（Order Dispatch Tester）是一个只用 Python 标准库的本地 Web 程序，用来给 AGV 调度做压力和死锁测试：按订单模板生成测试单，限流分批下发，持续看每张单和每台车，把「已分到车、又长时间没变化」的单标成疑似卡死。

它从单文件的 `rds_tester.py`（v1，只对接仙工 RDS 的固定五段死锁单）拆出来。核心不再写死某一种调度协议，RDS 与 M4 各是一个适配器。版本见 `order_tester/version.py`：`2.1.0`，`BUILD_DATE` 为 `2026-10-29 08:10 UTC`。许可证是 MIT，版权人 Ross Li（见 `LICENSE`）。

默认绑在 `127.0.0.1:5088`，给维护者自己在浏览器里用。它不是给现场操作员用的多用户服务。谁在用、现场有几套调度：待补。

## 架构

```
run.py / python -m order_tester
        └─ order_tester/server.py     标准库 HTTP，页面 + /api/*
                └─ order_tester/core.py
                      设置、服务器分桶、模板库、草稿与批次、轮询、卡死、逐块下发
                      └─ templates.py          中立订单（与调度协议无关）
                      └─ adapters/
                            base.py            DispatcherAdapter
                            rds.py + rds_scene.py
                            m4.py  + m4_scene.py
                └─ static/index.html + app.js  无构建的前端
                └─ i18n/zh.json + en.json      界面字符串
```

数据目录（项目根，或 `ORDER_TESTER_DATA`）里有 `settings.json`、`drafts.json`、`sent_orders.json`、`templates/<serverId>/`、`scene_cache.json`、`logs/`、`maps/`、`pointcloud_cache.json`。这些都不进 git。

### 适配器

`adapters/__init__.py` 的 `ADAPTERS` 现为 `rds` 与 `m4`。核心只调用 `DispatcherAdapter`：把中立订单变成 payload、提交、查状态、取消、拉机器人，以及可选的场景和地图。逐块下发是可选能力（`supports_incremental`）。两个适配器都实现了。

RDS（`rds.py`）走调度自己的 HTTP：`/scene`、`/downloadScene`、`/setOrder`、`/orderDetails/<id>`、`/robotsStatus`、`/terminate`，逐块时还有 `/addBlocks`、`/markComplete`。一块 RDS block 对应模板里的一个启用步骤。

M4（`m4.py`）把同一份中立订单映射过去：RDS 运单 = M4 运单，RDS block = M4 step，RDS `complete` = M4 `stepFixed`。创建、追加、封口、查询、取消的路径写在该文件头。认证是请求头 `xyy-app-id` / `xyy-app-key`，或 `POST /api/sign-in` 的会话 cookie。状态先映射成与 RDS 相同的内部名字，核心不必认识 M4 的原状态。场景几何在 `m4_scene.py`；点云 `.smap` 的解析复用 `rds_scene.decode_smap`。

本地假服务：`tools/fake_rds.py`（默认 18088）、`tools/fake_m4.py`（默认 18090）。

### 模板与中立订单

`templates.py` 描述有序步骤。位置来源是 `pool`（命名站点池）、`pre`（另一步骤所在站点的前置点）、`fixed`（固定站点）。生成策略在同一文件：`random`（默认，无放回）、`round_robin`、`cartesian`。`build_order` 产出中立订单：`id`、`template`、`picks`、`steps`（含 `location` / `operation` / `args`）、`preChosen`、`binChosen`，以及优先级、车辆、组、label。

内置 `default` 是原来的五段 RDS 死锁单：前置点 Wait → ForkLoad → Script → ForkUnload → ForkHeight。`tests/test_regression.py` 用 `tests/legacy_reference.py` 对照，要求 setOrder JSON 在相同种子下一致，包括键顺序。

args 字符串里的变量（`{start}`、`{end}`、`{orderId}`、`{preOf:<步骤>}` 等）在 `substitute` 里替换，未知变量报错。M4 且该池步骤走库位时，`{<池名>}` 是解析出的库位名；`{stationOf:…}` 和前置点仍是站点。

### 前端与 i18n

页面是一张 `index.html` 加 `app.js`，没有打包。页签：配置与派单、地图、机器人、测试订单。配置与派单下有连接、站点池、订单模板、派单参数与生成。左栏是服务器列表。

字符串在 `order_tester/i18n/{zh,en}.json`，`i18n.py` 读取，缺键回退中文，默认中文。`tools/i18n_src.py` 曾经用来生成这两份 JSON，现已过时，运行会覆盖现行文案。

### 服务器进程里还有什么

`server.main` 做一次性迁移（扁平 settings → 服务器列表、旧模板、variableShape），恢复草稿和已下发订单，然后起两个守护线程：`poller`（按轮询间隔看未结束的单和车）和 `inc_worker`（按逐块轮询间隔追加块）。卡死：单未结束、已有车辆、无变化时间超过阈值。车辆位移超过 5 cm 或转角超过 2° 算有变化（`MOVE_EPS_M`、`MOVE_EPS_DEG`）。未分到车的单不计卡死。

## 关键设计与理由

这些是维护者核实过、并已经写进代码的决定。编码时按 [AGENTS.md](../AGENTS.md) 守住，不要用「更干净的模型」换掉。

### 逐块下发只在运单终态停止

RDS 会短暂把运单报成 `FAILED`，随后又回到 `RUNNING`。若 `FAILED` 或 `Error` 就停止追加，测试单会停在半截。所以只有运单 `FINISHED` 或 `STOPPED` 才停止追加；`FAILED`、`Error` 以及其他非终态只暂停、继续轮询，恢复后再追加。在本工具里取消，调度侧成为 `STOPPED`，追加停止。

上一块要 `FINISHED`（或块状态 `MANUAL_FINISHED`）才发下一块。M4 侧对应：只有 Done（`FINISHED`）和 Cancelled（`STOPPED`）停止追加；`fault: true` 映射为 `FAILED`，只暂停。

`core.py` 的 `INC_STOP` 还包含取消类名字（`CANCELED`、`CANCELLED`、`TERMINATED`、`WITHDRAWN`、`SKIPPED`），与「取消即停」一致。查询失败、查无此单、追加接口连续失败都继续轮询；连续 5 次失败只是开始打告警。旧版本误把 `FAILED` 标成已停止的记录，启动或下一次逐块轮询时会恢复追加。

轮询是否还在看这张单，用适配器的 `terminal_states`。RDS 的这组集合比逐块的 `INC_STOP` 多一个块级的 `MANUAL_FINISHED`，并且同样不含 `FAILED`。

### 库位不写进模板

库位挂在某个站点的 `bins` 上，不是地图上的另一个点，也经常被路径挡住，不能靠名字下拉来选。模板因此不出现 `Loc-…`。

`站点池` / `固定站点` 先确定站点，再选走点位或走库位（`location.target` 为 `station` 或 `bin`）。走库位只在该站的 bins 上套用和前置点相同的选择标准：没有库位就回退走点位，只有一个就用那一个，有多个才用 `select` / `selArg`。这样同一份模板可以换场景，不必改库位名。

M4 下发时把解析出的库位名放进步骤 `location`（导航目标就是这个字符串）。RDS 协议仍要站点名，所以 RDS 的 `location` 保持站点，选中的库位记在 `binChosen`，两边用同一份模板时不会把 RDS 订单发歪。

旧模板里的 `location.bin="Loc-…"` 在校验时丢弃，并保持走点位。自动改成走库位会改变已经在用的单。

`opMode=binTask` 只表示 `rbkArgs` 里带动作名、不带普通参数。它可以和「去某个库位」同时出现，互不代替。

### 场景进来之后重画步骤表

走库位的选择框取决于该站有几个库位，而个数来自场景写进 `stMap` 之后的查询。若只更新站点表、不重画已打开的模板，步骤表会停在「尚未有场景」的样子。因此 `setScene` 末尾调用 `refreshStepsForScene`。打开页面时的缓存、手动加载、切换服务器后的缓存，都走 `setScene`。

### 一套参数绑在一条调度地址上

维护者会连不同的调度，参数不能串。`settings.json` version 2 用 `servers[]`：每一条有自己的地址、适配器、站点池、当前模板、派单选项、M4 认证和场景。语言全局，因为那是界面语言，不是现场参数。草稿、已下发、场景缓存、模板目录按服务器 id 分开，切换时清空内存再加载，避免上一套的点和单留在地图上。

界面上只有一个「调度系统地址」。RDS 与 M4 用同一格；选哪种，就显示哪种才有的项（M4 的认证和场景、RDS 的 variableShape、M4 的 keepFinalPathSpace）。两条地址并排，或在一条服务器里再做多套 M4 配置切换，都会让人搞不清当前到底连着谁。存储里的 `m4.profiles` 仍在，活动 profile 的地址同步到该服务器的 `base`。新建的服务器从空地址和 RDS 开始，避免把上一条的 M4 认证继承过去。

### 其他已落地、不宜悄悄改掉的选择

- 标准库 HTTP 和单页前端：本机工具，不引入依赖和构建。
- `FAILED` 继续轮询：RDS 可恢复；未结束且已分车时仍可被判卡死。连续三次「查无此单」（且不是网络错误）才记为 `CANCELED`（调度侧已无此单）。这是轮询终态，与逐块暂停不是同一条路径。
- 首次启动把 v1 的固定表单迁成 `templates/default.json`，并备份 `settings.json.bak-v1`。扁平 settings 迁成服务器列表时备份 `settings.pre_server.json`。迁移要可重复执行，不要删备份逻辑。
- 地图上的点和线来自调度场景，不要求用户再上传一份 `.smap`。

## 当前状态

- 适配器：RDS、M4。注册名就是 `rds`、`m4`。
- 本环境执行 `python3 -m unittest discover -s tests`：121 项通过（约 57 秒）。
- 没有 CI 配置。
- 根目录 `README.md` / `README.zh-CN.md` 仍写「目前只有 RDS 适配器」，和代码不符。使用说明 `docs/USAGE.*.md` 已包含 M4 和库位。是否另改 README：待补。
- `docs/USAGE.zh.md` 与 `docs/USAGE.en.md` 的逐块下发已与 `core.py` 对齐：连续失败满 5 次、查无此单都只暂停并继续轮询；只有运单 `FINISHED` / `STOPPED`（含在工具里取消）才终止追加。说明与代码再有出入时，以 `core.py` 为准。

## 待办

- 产品上下一版要做什么：待补。README 里提到以后可以加 VDA 5050 一类适配器；代码里没有，是否仍要做：待补。
- 是否在单独的文档改动里修正 README 的适配器范围：待补。
- 版本号何时从 `2.1.0` 递增：待补。
- 维护者从 box 同步到 Windows 笔记本的具体拷贝命令：待补。部署约定本身见 [AGENTS.md](../AGENTS.md)（测完再同步、重启 5088、备份到笔记本上 `D:\backups\odt\<时间戳>`，不写服务器 IP）。
