# 订单派发测试工具 (Order Dispatch Tester)

[English](README.md)

> 详细使用说明：[中文](docs/USAGE.zh.md) | [English](docs/USAGE.en.md)（**每次功能改动必须同步更新中英文两个版本**）。


一个只用 Python 标准库的小型 Web 工具，用于 **AGV 调度系统的压力 / 死锁测试**：
按可配置的 **订单模板** 生成测试订单，分批限流下发，持续监控每个订单和车辆，并标出疑似卡死（可能死锁）的订单。

目前实现的调度适配器是 **仙工 RDS**。核心逻辑与调度系统无关，以后可以增加 VDA 5050 等适配器。

## 功能

- **订单模板**：有序的步骤列表；每步包含位置来源（命名站点池 / 另一步骤站点的前置点 / 固定站点）、动作 operation、
  支持变量替换的参数 args、可选 `variableShape`、启用开关。内置 `default` 模板 = 原来的五段 RDS 死锁测试单
  （取货前置点 Wait → ForkLoad → Script → ForkUnload → ForkHeight）。
- **命名站点池**（默认 `start` 起点 / `end` 终点，可新增任意池），池互换、单个站点删除，从站点表或地图点击加入。
- **生成策略**：随机不重复（默认，订单数默认 = 第一个池的大小）、轮询、全组合（笛卡尔积）。
- **模板编辑器**：列表 / 新建 / 复制 / 删除 / 导入 / 导出（`templates/*.json`），步骤增删、排序（按钮或拖动）、启用，
  逐步表单或 JSON 编辑模式，实时预览示例订单（调度系统实际收到的 JSON）。
- **批次**：先生成待下发，再勾选按间隔和最大未完成数下发；按批次分组显示，带统计、筛选、排序、开始/结束/执行时长列。
- **卡死判断**：已分配车辆且 N 秒无任何变化即疑似卡死。`FAILED` **不是**终态（RDS 可恢复），未分车的订单不计，
  车辆位移 > 5 cm 或转角 > 2° 视为有变化。
- **地图**（路线与点云来自调度系统场景 / `/downloadScene`，无手动上传 `.smap`），**机器人**按组显示。
- **中文 / 英文界面**，右上角切换并保存，默认中文。

## 运行

Python 3.8+，无第三方依赖。

```sh
python run.py --port 5088 --rds http://<rds-host>:8088
# 或
python -m order_tester --port 5088
```

浏览器打开 <http://127.0.0.1:5088>。Windows 下双击 `start_tester.bat`（用 `pythonw` 后台运行并打开浏览器；
如果 `pythonw.exe` 不在 PATH 中，设置环境变量 `PYW` 为其完整路径）。

参数：`--port`、`--host`（默认 127.0.0.1）、`--rds/--base` 调度系统地址、`--data DIR`（`settings.json`、`drafts.json`、
`sent_orders.json`、`templates/`、`logs/`、`maps/` 所在目录，默认为项目目录，或环境变量 `ORDER_TESTER_DATA`）、
`--adapter`（默认 `rds`）。

## 配置 RDS 地址

启动时加 `--rds http://<rds-host>:8088`，或在页面 **配置 → 调度系统地址** 填写后点保存（写入 `settings.json`）。
只有在加载场景、下发、取消以及监控已下发订单时才会访问 RDS。

## 模板

模板是 `<data>/templates/` 下的 JSON 文件。首次启动时会生成 `default.json`（如有旧版 `settings.json` 则按旧设置迁移，
否则使用内置默认）。示例见 `examples/templates/`。格式见英文 README 的示例。

- `location.type`：`pool`（按策略从命名池取站点）、`pre`（另一步骤站点的前置点：先查手动映射，再用场景 AP→LM 推导）、`fixed`（固定站点，可选 `bin`）。
- 站点池条目是站点名字符串，或选了该站点上的库位时为 `{"station","bin"}`。M4 会把步骤 `location` 写成库位名；前置点和「同一单内站点不重复」仍按站点。RDS 仍发送站点名。库位目标与 `opMode=binTask` 不是一回事。
- `operation: "none"` 表示只移动。可选 `blockSuffix` 指定 RDS blockId 后缀（默认 `-<id>`）。
- args 中的变量：`{start}`、`{end}`、`{<池名>}`、`{pickPre}`、`{dropPre}`、`{pre:<池名>}`、`{stationOf:<步骤ID|stepN>}`、
  `{preOf:<步骤>}`、`{orderId}`；未知变量会报错。
- 各池按步骤顺序取点；勾选“同一单内站点不重复”时同一订单内不会重复使用同一站点。

## 调度适配器接口

`order_tester/adapters/base.py` 定义 `DispatcherAdapter`，`order_tester/adapters/rds.py` 为 RDS 实现
（`/scene`、`/downloadScene`、`/setOrder`、`/orderDetails/<id>`、`/robotsStatus`、`/terminate`）。
主要方法：`build_payload`（中立订单 → 调度系统 JSON）、`submit`、`order_status`（归一化状态）、`cancel`、`robots`，
以及可选的场景/地图方法；`terminal_states` 为停止轮询的状态（RDS 中 FAILED 不是终态）。
新增调度系统：继承 `DispatcherAdapter`，在 `order_tester/adapters/__init__.py` 的 `ADAPTERS` 注册，用 `--adapter <名称>` 启动。

## 从 rds_tester.py (v1) 迁移

把 `settings.json`、`drafts.json`、`sent_orders.json`（可选 `logs/`、`maps/`）复制到数据目录后启动即可。首次启动时：

- 旧的固定表单（起终点 operation/args、Script、升叉、取货前置点 Wait、每段 variableShape）转换为 `templates/default.json`，
  生成的 setOrder JSON 与旧版逐字节一致；
- `starts` / `ends` 转为 `pools.start` / `pools.end`，设置 `activeTemplate`，备份为 `settings.json.bak-v1`，旧键保留；
- 待下发 / 已下发订单在加载时补充 `picks` / `template` / `adapter` 字段；旧版误标为结束的 FAILED 订单会重新监控；历史批次按日志重建。

## 测试

```sh
python -m unittest -v
```

包含回归测试（用原版 `build_order` / `Picker` / `make_draft`（`tests/legacy_reference.py`）与新模板引擎在相同随机种子和输入下
比较，要求 JSON 完全一致，含键顺序）、迁移测试、模板/策略测试，以及针对 `tools/fake_rds.py`（可手动运行的简易假 RDS）的端到端测试。

界面文字在 `order_tester/i18n/{zh,en}.json`，直接编辑这两个文件。`tools/i18n_src.py` 是遗留的生成脚本，已过时；不加 `--force` 拒绝运行，因为运行它会覆盖当前界面文字。

## 许可证

MIT 许可证，详见 [LICENSE](LICENSE)。Copyright (c) 2026 Ross Li。
