# AGENTS.md

本文件给 Cursor、Claude Code 以及其他会读仓库的编码工具。改代码前先读完。项目背景在 [docs/PROJECT.md](docs/PROJECT.md)。给人看的操作说明是 [docs/USAGE.zh.md](docs/USAGE.zh.md) 和 [docs/USAGE.en.md](docs/USAGE.en.md)。

仓库是公开的。看不出、本文件也没写明的流程、地址、排期，标「待补」，不要编。

## 公开仓库

- 绝不提交内部 API 文档、服务器地址、凭据、现场数据（真实场景、现场库位清单、现场模板、日志）。
- 文档里的调度地址只用占位符，例如 `http://<rds-host>:8088`。不要写 IP 或真实主机名。
- 运行时数据默认在项目根目录，或环境变量 `ORDER_TESTER_DATA` 指向的目录。`.gitignore` 已忽略 `settings.json`、`drafts.json`、`sent_orders.json`、`templates/`、`logs/`、`maps/`、`scene_cache.json`、`pointcloud_cache.json` 以及 `*.bak*`。不要把这些加进提交。
- M4 的应用密钥和密码只留在已被忽略的 `settings.json`，或环境变量 `ODT_M4_APP_ID`、`ODT_M4_APP_KEY`、`ODT_M4_USER`、`ODT_M4_PASSWORD`、`ODT_M4_SCENE`。`/api/settings` 和 `/api/m4` 里显示为 `******`，日志不写。界面上回传的 `******` 表示沿用已保存的值。
- 示例模板只放 `examples/templates/`。`tools/fake_m4.py` 里的 `mock-app` / `mock-key` / `mockuser` / `mockpass` 是假数据。不要换成现场口令，也不要另写一份真实连接说明。
- 适配器源码文件头里已有的 HTTP 路径可以保留。不要把内部 wiki 或接口文档正文抄进仓库。

## 运行与测试

Python 3.8+，只用标准库。没有 `requirements.txt`、`pyproject.toml`，也没有构建步骤。编写本文件时用 Python 3.12.3 跑通下面的测试。仓库里没有 `.github/workflows`，没有 CI。

已用 `--help` 核对过的入口：

```sh
python3 run.py --port 5088
python3 -m order_tester --port 5088
```

两者都进 `order_tester.server.main`。参数：`--port`（默认 5088）、`--host`（默认 `127.0.0.1`）、`--rds` / `--base`（调度地址）、`--data`（数据目录，默认项目根，或 `ORDER_TESTER_DATA`）、`--adapter`（`rds` 或 `m4`；省略时用当前服务器 settings 里的 `adapter`，再否则 `rds`）。浏览器打开 `http://127.0.0.1:5088`。启动时先套用当前服务器 settings 里的 `base`；命令行如果带了 `--rds` / `--base`，覆盖本次进程的地址（`set_base(None)` 表示不改）。M4 的地址来自该服务器的 M4 profile，不走这条 RDS 的 `base` 覆盖（`M4Adapter.base_from_settings` 为假）。页面上保存会写回当前服务器。

脚本：`start_tester.sh` 执行 `python3 run.py --port ${PORT:-5088}`。Windows 的 `start_tester.bat` 在 5088 未被占用时用 `pythonw run.py --port %PORT%` 后台启动并打开浏览器；`pythonw.exe` 不在 PATH 时设置环境变量 `PYW`。

假调度（测试也会拉起它们）：

```sh
python3 tools/fake_rds.py                  # 默认端口 18088；另有 --scene-delay / --scene-fail / --scene-nolen / --download-scene
python3 tools/fake_m4.py --port 18090      # 默认端口 18090；--no-auth 可关认证
```

测试（本环境已跑通，121 项，约 57 秒）：

```sh
python3 -m unittest discover -s tests
```

加 `-v` 可看用例名。README 另写了 `python -m unittest -v`（`tests` 是包）。本次实际跑通的是上面的 `discover`。没有 pytest 配置。不要为了跑测试增加依赖。

和下列行为有关的改动，至少要让对应测试继续通过：`tests/test_regression.py`（默认模板与旧版 setOrder JSON）、`tests/test_migration.py`、`tests/test_incremental.py`、`tests/test_bins.py`、`tests/test_m4.py`、`tests/test_ui_static.py`（含 `setScene` → `refreshStepsForScene`）、`tests/test_servers.py`。

## 功能变更必须同步两份使用说明

界面、字段或行为有变化时，同时更新 `docs/USAGE.zh.md` 和 `docs/USAGE.en.md`，两份说的是同一件事。

英文功能名、按钮名与英文界面字符串一致。以 `order_tester/i18n/en.json` 为准，例如：

| 中文 | `en.json` |
|---|---|
| 站点池（位置来源） | Pool（`loc.pool`） |
| 固定站点 | Fixed station（`loc.fixed`） |
| 走点位 / 走库位 | Station / Bin（`tgt.station` / `tgt.bin`） |
| 调度系统地址 | Dispatcher URL（`cfg.base`） |
| 逐块下发 | Block-by-block（`disp.bbb`） |
| 下发选中 | Send selected（`ord.send`） |

`tools/i18n_src.py` 是过时生成器。文件头写明：不加 `--force` 会拒绝运行；运行会用旧字符串覆盖 `order_tester/i18n/zh.json` 和 `en.json`。不要运行它，也不要按它改界面。界面字符串直接改这两个 JSON，键集合保持一致。`en.json` 与 `i18n_src.py` 冲突时，以 `en.json` 为准。

只改说明、不改行为时，不必改 USAGE。本次及以后的纯注释、纯智能体说明，也不要顺手改功能代码。

## 必须守住的行为

### 逐块下发

维护者核实的规矩：只有订单 `FINISHED` 或 `STOPPED` 算终态。`FAILED`、`Error` 以及其他状态都不能停止追加块，只暂停并继续轮询。在本工具里取消，会使调度侧进入 `STOPPED`，那才停止追加。

实现在 `order_tester/core.py` 的 `inc_once`：

- `INC_STOP` 除 `FINISHED`、`STOPPED` 外，还有取消类状态 `CANCELED`、`CANCELLED`、`TERMINATED`、`WITHDRAWN`、`SKIPPED`。这是「取消即停」，不是把 `FAILED` 当终态。
- 上一块是 `FINISHED` 或 `MANUAL_FINISHED`（`INC_BLOCK_DONE`）才追加下一块。
- 运单或块 `FAILED` / `Error`、`SUSPENDED`、未知状态、查询失败或超时、查无此单、`addBlocks` / `markComplete` 失败：记 `inc_warn`，状态保持 `appending`，下一轮再试。`INC_ERR_LIMIT = 5` 只是开始显示「仍在重试」的告警。
- 旧数据里因 `order FAILED` 等非终态被标成 stopped 的，`inc_revive` 会改回 `appending`。原因以 `setOrder:` 开头的（首次下发就没建成）不复活。

轮询用的终态是另一套，同样不要把 `FAILED` 算进去：`RdsAdapter.terminal_states` 含 `FINISHED`、`STOPPED`、`MANUAL_FINISHED`、`CANCELED` / `CANCELLED`、`WITHDRAWN`、`TERMINATED`、`SKIPPED`，不含 `FAILED`。`M4Adapter.terminal_states` 只有 `FINISHED` 和 `STOPPED`（M4 的 Done / Cancelled）；`fault: true` 映射成 `FAILED`，只暂停。

`docs/USAGE.zh.md` 与 `docs/USAGE.en.md` 的「逐块下发」里，有句子和上述代码不一致（连续失败 5 次就停止、查无此单就停止）。改这块行为或改这两段时，以本节和 `core.py` 为准，两份 USAGE 一起改齐。

### 库位

- 模板不点名具体库位，不要做 `Loc-…` 下拉，也不要把库位名写进模板。
- `站点池`（Pool）和 `固定站点`（Fixed station）选出站点后，旁边是「走点位 / 走库位」（Station / Bin）。字段 `location.target`：省略或 `station` 为走点位，`bin` 为走库位。`pre` 步骤没有这个字段。
- 走库位只看该站的 `bins`，不扫全图。0 个：回退走点位，`binChosen` 记 `fallback: station`。1 个：直接用，`select` 记 `only`。多个：复用前置点的 `select` / `selArg`（`nearest` / `index` / `name` / `dir` / `random`）。同一单内，同一站点加同一策略只选一次。
- M4（`build_order(..., bin_targets=True)`）把解析出的库位名写入步骤 `location`。RDS 仍发送站点名，解析结果只留在订单的 `binChosen`。
- 前置点，以及「同一单内站点不重复」，按站点，不按库位名。
- 旧模板 `location.bin="Loc-…"`：`templates.validate` 丢掉 `bin`，并保持走点位。已写 `target=bin` 的步骤不会被改回走点位。旧名字不会变成 `select=name`。
- 库位目标与 `opMode=binTask` 不是一回事。`binTask` 只决定发动作名，还是动作名加参数。

### 场景加载后重画已打开的模板

`order_tester/static/app.js` 里 `setScene` 在写入 `stMap` 之后调用 `refreshStepsForScene`。已打开模板的步骤表要按新场景重画：多个库位才出现选择标准，0 个或 1 个显示对应说明。页面打开时的缓存、手动加载、切换或删除服务器后的缓存恢复，都要走 `setScene`。不要另写一条只更新站点表、不刷新 `#steps` 的路径。`refreshStepsForScene` 在焦点还在 `#steps` 里时会延后重画，避免打掉正在编辑的控件。

### 参数按服务器隔离；一条调度地址

`settings.json` 为 version 2。`lang` 是全局的（右上角中/英，默认中文）。地址、适配器、站点池、当前模板、派单选项、M4 认证和场景，都在 `servers[]` 的当前条目里。保存只写当前服务器。

草稿、已下发订单、场景缓存按服务器 id 分桶（`drafts.json`、`sent_orders.json`、`scene_cache.json`）。模板在 `<data>/templates/<serverId>/`。切换服务器会清掉内存里的订单、机器人和地图，再加载那一条的桶。

界面只有一个调度地址框（Dispatcher URL）。选 RDS 或 M4 后显隐对应选项：M4 才显示 `#m4box`（场景、应用 ID/密钥或用户名/密码）；步骤表的 variableShape 列只在 RDS 显示；`keepFinalPathSpace` 只在 M4 显示。不要做成两个并排地址，也不要在同一条服务器里做多套连接配置的切换界面。

存储里仍有 `m4.profiles`（当前活动 profile 的 `base` 会同步到该服务器的 `base`，侧栏显示这一条）。没有维护者同意，不要删这个结构。新建服务器在 `add_server` 里固定为 RDS、空地址，并种入内置 `default` 模板；传入的 adapter 会被忽略。

## 代码约定

- 新代码贴着所在文件：`# -*- coding: utf-8 -*-`，紧凑写法，注释用英文。不要为了风格大范围重排。
- 调度 I/O 只走 `order_tester/adapters/`。`DispatcherAdapter` 在 `base.py`，注册表在 `adapters/__init__.py` 的 `ADAPTERS`（现为 `rds`、`m4`）。中立订单由 `templates.build_order` 产生，适配器再变成各自的 payload。
- 核心、轮询、卡死判断、逐块状态机在 `order_tester/core.py`。HTTP 在 `order_tester/server.py`（标准库 `ThreadingHTTPServer`）。前端没有构建步骤：`order_tester/static/index.html` 与 `app.js`。静态响应带 `Cache-Control: no-store`，首页给 `app.js` 加上修改时间查询参数。
- 界面文案只放 `order_tester/i18n/zh.json` 与 `en.json`。`order_tester/i18n.py` 缺键时回退中文。
- 版本在 `order_tester/version.py` 的 `VERSION`、`BUILD_DATE`，以及 `order_tester/__init__.py` 的 `__version__`。何时递增：待补。
- 内置 `default` 模板须继续通过 `tests/test_regression.py`：与 `tests/legacy_reference.py` 在相同种子和输入下，setOrder JSON 一致（含键顺序）。不要为了整理字段顺序去改它。

## 不能动

- 不经维护者明确同意，不删除文件、接口、迁移和旧字段兼容。包括但不限于：`starts` / `ends`、`location.bin`、`blockSuffix`、`args.m4Mode`、`settings.json.bak-v1`、`settings.pre_server.json`、`sent_orders.pre_server.json`、按服务器分桶、`m4.profiles`。看起来没用，不算可以删。
- 不改上面「必须守住的行为」来简化实现。
- 不把 `tools/i18n_src.py` 重新接成文案源。
- 不提交运行时数据、凭据、现场数据、内部接口文档、服务器地址。

## 部署

维护者在自己的 box 上测完，再把程序同步到 Windows 笔记本的工作目录，并重启监听 5088 的进程。更新前把当时的工作目录备份到该笔记本上按时间戳命名的目录；维护者用的路径是 `D:\backups\odt\<时间戳>`。文档、提交和日志里不要写任何服务器 IP。

USAGE 里的更新步骤是：替换程序文件（先备份）→ 结束旧的 `run.py --port 5088` → 用 `pythonw run.py --port 5088` 再起 → 访问首页确认 200。数据目录（模板、站点池、订单）留在原地。从 box 拷到笔记本的具体命令：待补。
