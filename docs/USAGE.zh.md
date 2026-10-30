**中文** | [English](USAGE.en.md)

# 订单派发测试工具 使用说明

> 维护约定：**每次功能改动都要同步更新本文档**（新增/修改的界面、字段、行为），**并同步更新英文版 [USAGE.en.md](USAGE.en.md)**。两个语言版本必须保持一致。

[项目 README](../README.zh-CN.md) · [English README](../README.md)

## 1. 启动与部署

- 依赖：Python 3.8+，仅标准库。
- 启动：`python run.py --port 5088 --rds http://<rds-host>:8088`，浏览器打开 <http://127.0.0.1:5088>。
  - 参数：`--port`、`--host`（默认 127.0.0.1）、`--rds/--base` 调度系统地址、`--data DIR` 数据目录（默认项目目录，或环境变量 `ORDER_TESTER_DATA`）、`--adapter`（默认 `rds`）。
  - 数据目录内容：`settings.json`（含 `servers` 列表与 `currentServerId`；仅 `lang` 为全局）、`drafts.json` / `scene_cache.json` / `sent_orders.json`（按服务器 id 分桶）、`templates/`（共享模板库；**当前激活模板**按服务器）、`logs/`、`maps/`。
- Windows：双击 `start_tester.bat`（用 `pythonw` 后台运行并打开浏览器；`pythonw.exe` 不在 PATH 时设环境变量 `PYW`）。
- 页面里保存的调度系统地址（写入 `settings.json`）优先于启动参数 `--rds`。
- 更新部署：替换程序文件（先备份）→ 结束旧的 `run.py --port 5088` 进程 → 重新以 `pythonw run.py --port 5088` 后台启动 → 访问首页确认 200。数据目录（模板、站点池、订单）不受影响。
- 自测：`python -m unittest -v`；`tools/fake_rds.py` 是假 RDS（`--port`、`--scene-delay 秒` 模拟慢场景、`--scene-fail` 模拟失败）。

## 2. 配置与派单（四个子页）

顶部子标签切换，当前子页记在浏览器 localStorage。所有子页顶部常驻一行**摘要**：当前模板 · 各使用中站点池的站点数 · 策略 · 计划单数，旁边有**生成运单**按钮（与第 4 子页的按钮相同）。

### 2.1 连接
- **全局左侧服务器列表**：位于所有主页签（配置与派单 / 地图 / 机器人 / 测试订单）左侧的共用栏；**应用标题**（订单派发测试工具）也在该左栏顶部，与服务器列表同宽，右侧以竖向分隔线与页签栏/主内容分开。每个条目是一套独立参数（地址、适配器、站点池、当前模板、派单选项、M4 认证/场景等）。点击一行切换当前服务器；当前页签右侧内容会按该服务器的参数重载。保存只写入当前服务器，不会覆盖其它服务器。
  - **添加 / 改名 / 删除**：删除需确认，且至少保留一个服务器。新服务器须填写名称（不可空）；使用空默认值（空地址/空站点池/空测试订单与草稿；可先填地址再保存），并自动写入内置 `default` 订单模板为当前模板；`sent_orders.json` 按服务器分桶，切换或新建不会串单。切换服务器时清空机器人列表与地图缓存，直至新适配器返回数据。
  - **折叠/展开**：列表右缘的 « / » 箭头可收起为细条以腾出横向空间；展开后行为与原先相同。折叠状态记在浏览器 localStorage（`odtSrvCollapsed`），刷新后仍有效。
- 「配置与派发」右侧：调度系统地址、轮询间隔（秒）、卡死阈值（秒）、车辆静止阈值（秒）、调度适配器。界面语言在右上角切换（中/英），**语言为全局**，不随服务器切换。
- **调度系统**：`RDS`（默认）或 `M4`。切换立即生效，并保存在**当前服务器**的 `settings.json` 条目中。选 RDS / M4 后显示对应选项（M4 才出现当前服务器的认证与场景；不再有多配置切换 UI——连接按左侧服务器分条保存）。详见下文"M4 调度系统"。
- 旧版扁平 `settings.json` 首次启动会迁移为带 `servers` 列表的结构，并备份为 `settings.pre_server.json`；原参数落在以当时地址命名的一条服务器下。

### 2.2 站点池
- **从调度系统场景加载站点**：**唯一的手动加载场景入口**。一次性从当前调度系统拉取站点、前置点、机器人组、场景几何（路线，按曲线类型镶嵌）和点云（RDS：`/scene` 的 `normalPosList`，必要时 `/downloadScene`；M4：场景 schema 中的 `normalPosList`，否则用 `groupsMap.mapFile` 的 `GET /api/fleet/scenes/{sceneId}/download/{mapFile}`），总是重新拉取；地图页直接复用结果（见第 7 节）。
- 站点表只读，可搜索、按类型过滤，显示坐标和前置点，只列出已加入池的站点（见下文「站点池页的站点列表（只读）」）。往池里添加站点只有两种方式：在「地图」页点击站点，或用「手动粘贴站点」(逗号/换行分隔站点名)。
- **站点池**：默认 `start`（起点）、`end`（终点），可新建任意池（字母/数字/下划线，不以数字开头）、改名（自定义池，模板中引用会同步更新）、删除池、互换两个池、点 × 删除单个站点。当前模板没用到的池标注“(当前模板未使用)”。
- **“使用中”的池**只看**启用**的步骤：启用的 `站点池` 步骤所用的池，以及启用的 `前置点` 步骤（沿引用链）最终指向的池。只被禁用步骤引用的池（例如把取货/前置 Wait 都禁用、只保留放货的“仅终点”模板中的 `start`）不算使用中：摘要不显示、生成/自动派单不要求非空、运单的站点列只显示终点（此时 `pickPre` 为空）。站点池为空的校验（前端与后端）只针对使用中的池。
- **生成策略**：随机不重复（默认单数 = 第一个池大小）、轮询（第 i 单取各池第 i 个，单数 = 最大池）、全组合（笛卡尔积）。
- 选项：同一单内站点不重复；同一批内尽量不重复使用站点（无放回）。

### 2.3 订单模板
- **左右布局**：左侧为模板列表（点选切换当前模板），底栏按钮：新建 / 复制 / 删除 / 导入 / 导出（文件在 `<data>/templates/*.json`）；右侧为当前模板内容。
- **模板名称**可在右侧直接编辑（改完即重命名并持久化；需合法名）；说明（`#tpl_title`）仍可编辑。
- **动作模式（按步）**：步骤表「动作」旁有下拉 `binTask` | `operation`（M4 与 RDS 通用，同一模板可混用）。`binTask` = 只发动作名、不带参数（参数列隐藏）；`operation` = 动作名 + args。新建步骤默认 `binTask`。无全局「步骤动作字段」总开关。
- 步骤表可添加、删除、启用/停用、按钮或拖动排序；**删除按钮在首列**（与拖动柄/上下移放一起）。可切换 JSON 编辑模式；下方可折叠的示例订单预览（调度系统实际收到的 JSON）。字段见第 3 节。
- **variableShape 列仅 RDS 显示**（M4 时表头与单元格隐藏）；切换调度系统时会刷新显隐。
步骤表列顺序：步骤表：位置来源 → **模式** → **动作**（单输入框）→ **参数**（仅 operation 显示；binTask 隐藏参数）。

### 2.4 派单参数与生成
- 机器人组（RDS `group`，不指定则不带该字段）、指定车辆（留空=自动分配）、优先级、label（可选）。
- **逐块下发**（默认关闭）与 **逐块轮询(秒)**（默认 1）：见下文「逐块下发」。勾选状态随配置保存，对之后点击「下发」/自动派单生效。
- 前置点手动映射：每行 `站点=前置点`，一站多值写 `站点=前置点1|前置点2`（第一个为默认），优先于场景推导；也兼容 `站点:前置点`、`站点 前置点`，`#` 后为注释。写法不对（如 `AP1=LM1, LM2`、`AP1=`、同一站点写两行）会在输入框下方标红，生成时报错并指出行号。
- 订单数 N（勾“=默认”则跟随策略默认值）→ **生成运单**：只生成“待下发”，到“测试订单”页再下发。
- 若模板用到前置点而尚未加载场景，生成前会自动加载场景（带遮罩，失败弹窗）；无前置点的站点会提示并跳过。

## 3. 订单模板字段

| 字段 | 说明 |
|---|---|
| 启用 | 停用的步骤不生成块 |
| ID | **必填**，模板内唯一，不能为空或重复；用于变量引用。默认块/步骤后缀为 `-<ID>`（UI 只编辑 ID；旧模板若仍带 `blockSuffix` 字段，生成时继续兼容） |
| 说明（步骤 `name`） | 可选，仅显示用（可中文）；可空，不影响保存/校验。与模板级「说明」(`title`) 不同 |
| 位置来源 location | `站点池`（`{"type":"pool","pool":"<池名>"}`，按策略从池中取点，下拉列出全部池）；`另一步骤站点的前置点`（`{"type":"pre","step":"<步骤ID>"}`，先查手动映射，再用场景 AP→LM 推导）；`固定站点`（`{"type":"fixed","station":"<站点>"}`） |
| 前置点选择 select / selArg | 仅 `pre` 步骤。站点有多个候选前置点时选哪个，见下方「多个前置点」 |
| 动作 operation | 如 `JackLoad`、`JackUnload`、`ForkLoad`、`Wait`、`Script`；`none` 表示只移动 |
| 动作模式 opMode | `binTask`（仅动作名）或 `operation`（动作名 + 参数）；M4/RDS 通用，可按步混用。新建步骤默认 `binTask`。未写时：M4 回退配置/默认 `binTask`，RDS 回退 `operation`（兼容旧模板） |
| 参数 args (JSON) | 必须是 JSON 对象；多行编辑框，可纵向拖拽调整高度。`opMode=binTask` 时 UI 隐藏且下发忽略 |
| variableShape | 仅 RDS 显示该列；可选，勾“启用”后填 `head` / `tail`（数字，米），写入该块的 `variableShape`。M4 时隐藏 |
| 保持末段空间资源不释放 keepFinalPathSpace | 仅 M4 显示该列；勾选后该步骤带 `keepFinalPathSpace: true`（M4 运单步骤字段「保持末段空间资源不释放」），不勾选则不带。RDS 时隐藏 |

**args 变量**（字符串中替换，未知变量报错）：
`{start}` `{end}` `{<池名>}` 本单从该池取到的站点；`{pickPre}` `{dropPre}` 起/终点的前置点；`{pre:<池名>}` 该池站点的前置点；`{stationOf:<步骤ID|stepN>}` 某步骤的站点；`{preOf:<步骤>}` 某步骤站点的前置点；`{orderId}` 订单 ID。

### 多个前置点（前置点选择策略）

加载场景时，每个站点的**全部**候选前置点都会保存（含方向、距离、是否 LM，存入场景缓存），站点表「前置点」列下方按序号列出，例如 `1.LM1(驶入 1.0m) 2.LM2(驶入 3.0m) 3.LM3(驶出 2.0m)`。候选顺序：站点属性里指定的 → 驶入且为 LM → 驶出且为 LM → 其它驶入 → 其它驶出，同组内由近到远；第 1 个就是默认前置点（和以前一致）。

`pre` 步骤的「位置来源」下多了一个选择框（模板 JSON 里是 `location.select` / `location.selArg`）：

| 策略 | select / selArg | 含义 |
|---|---|---|
| 最近（默认） | 不写，或 `nearest` | 候选第 1 个；有手动映射时用手动的第一个。旧模板不受影响 |
| 按序号 | `index` / `2` | 第 N 个候选（从 1 开始） |
| 按名称/通配符 | `name` / `LM1*` | 第一个名字相同或匹配通配符（`*`、`?`）的候选 |
| 按方向 | `dir` / `in` 或 `out` | 第一个驶入（in）/驶出（out）的候选 |
| 每单随机 | `random` | 每单从候选中随机选一个 |

- 有手动映射时，候选列表 = 手动写的值（按写的顺序；方向/距离沿用场景信息，场景里没有的点方向未知，按方向选会匹配不到）。
- 变量也可带策略，写在 `@` 后：`{preOf:<步骤>@in}`、`{preOf:<步骤>@out}`、`{preOf:<步骤>@#2}`、`{pre:<池名>@name=LM1*}`、`{preOf:<步骤>@random}`；不带 `@` 时和以前一样。
- 同一单内，同一站点 + 同一策略只选一次（随机也一样），步骤和变量拿到的一致。
- 匹配不到时生成报错，指出步骤、站点、策略和全部候选，例如：`步骤 前置: 站点 AP2 没有符合 dir=out 的前置点 … (候选: LM20(in))`。
- 每单记录实际选中的前置点（订单记录里的 `preChosen`）；测试订单页「站点」列出现 ⓟ 时，鼠标悬停可看「步骤: 站点 → 前置点 (策略)」。
- 示例：`examples/templates/pre_select_demo.json`。

内置 `default` 模板 = 原五段 RDS 死锁测试单（前置点 Wait → 取货 → Script → 放货 → 升叉）。
启动时**仅在还没有任何模板**时创建 `default`；已有其它模板时（例如把 default 改名为 AnyPallet）不会再重建。**新建服务器**时也会在该服务器的 `templates/<serverId>/` 下写入一份 `default` 并设为当前模板；之后若用户删光模板则保持为空，不会再次自动播种。

## 地图页

- 图层：点云、路线、站点、车辆；「点云」旁可选点大小 细/中/粗/特粗（屏幕像素，缩放时保持不变），选择会保存（设置 + 浏览器）。
- 「站点朝向」图层：场景里带角度的站点画紫色朝向箭头（RDS 字段 `dir`，弧度；也识别 `angle`/`theta`/`yaw`），没有角度的站点不画；带 `ignoreDir=true`（不限朝向）的站点箭头画成浅色；鼠标悬停站点显示名称、类型和角度（度）。角度随场景缓存保存。
- 点云与路线均来自场景加载（见第 7 节）；**地图页不再提供**手动上传 `.smap` 或填写本机路径；RDS / M4 都从已连接的调度系统自动取场景地图。地图页本身不触发场景加载。
- 站点图层开启时画出站点名；LM 与 AP 均可点击加入站点池（M4 与 RDS 相同）。M4 路线按场景里的曲线类型（Straight / Bezier / DegenerateBezier / NURBS / Arc 等）镶嵌绘制，不是端点直线相连。

## 4. 机器人组

- 加载场景时从 `/scene` 解析机器人组；“派单参数”的机器人组下拉即来自这里。
- “机器人”页按组分区显示（无组的归“未分组”），列：坐标、当前站点、当前运单及状态、可调度、连接、阻挡、电量、静止时长；有运单且静止超过“车辆静止阈值”标红（疑似死锁）。

## 5. 测试订单页

- **分组**：待下发一组置顶；已下发按批次分组（新批次在前），组头显示批次时间、单数、各状态计数、卡死数、总时长；可折叠，可“全选本组（筛选后的）”。旧版下发的订单按日志或时间间隔推断历史批次。
- **下发**：勾选待下发 → 设本批间隔（秒）与最大未完成订单（0=不限）→ 下发选中；可停止下发、删除选中待下发、互换选中待下发的起终点（按当前模板重建）。
- **已下发**：取消选中、取消全部未完成（terminate）、清空已下发列表（待下发保留）、查看 JSON。
- **筛选**：状态多选（都不勾=全部）、车辆包含、机器人组、站点（匹配“起点→终点”）、订单 ID、只看疑似卡死、隐藏已结束、清除筛选；显示“匹配 n/总数”。
- 车辆、机器人组筛选只作用于已下发订单；未分配车辆/组的待下发仍会显示。
- **排序**：点表头切换升/降序（订单ID、站点、车辆、状态、创建时间、已运行、无变化、开始/结束时间、执行时长等），排序设置记在 localStorage。

## 6. 状态与卡死判定

- 状态：待下发、SENT、CREATED、TOBEDISPATCHED、RUNNING、WAITING、FAILED、FINISHED、STOPPED、SEND_FAIL 等。
- 终态（停止轮询）：FINISHED、STOPPED、MANUAL_FINISHED、CANCELED/CANCELLED、SKIPPED（以及下发失败 SEND_FAIL）。**FAILED 不是终态**（RDS 可恢复），继续监控并可被判卡死。
- **疑似卡死**：订单未结束、**已分配车辆**、且“无变化”时长 > 卡死阈值。状态/块状态变化或车辆位移 > 5 cm、转角 > 2° 都算有变化；未分配车辆的订单不计。卡死数显示在页签、组头和地图摘要上。

## 7. 场景加载与遮罩

- **加载入口**：
  - 手动：只有站点池页「从调度系统场景加载站点」（站点 + 前置点 + 机器人组 + 几何 + 点云一次加载，忽略缓存重新拉取）。
  - **场景缓存**：每次成功加载后，服务端把场景（站点、前置点、机器人组、路线、点云）保存在内存并落盘到 `<data>/scene_cache.json`（含加载时间），重启服务也在。加载失败不会覆盖上次成功的缓存。
  - 页面打开/刷新时**无条件从缓存恢复**，不访问 RDS、不显示遮罩；站点区和地图页状态行显示「场景加载于 HH:MM」（非当天加日期）。
  - 只有点「从调度系统场景加载站点」才重新从 RDS 拉取并更新缓存；生成运单优先使用缓存的前置点。
  - 无缓存时：页面打开若站点池非空会自动加载一次；生成运单需要前置点而尚未加载时自动加载。
  - 地图页**不再有**「重新加载场景/点云」按钮，也不会自己触发加载；未加载时状态行提示去站点池页加载。点云与路线只随站点池页的场景加载从调度系统获取（无手动 `.smap` 上传/路径）。
- **遮罩与进度条**：加载期间全屏半透明遮罩 + 转圈 +「正在加载场景…」，下方是进度条、当前阶段和已用秒数（中/英），阻止点击和键盘操作，完成后自动消失。
  - 阶段：请求 /scene（等待响应，进度条滚动）→ 下载场景（有 Content-Length 时显示百分比和 已下载/总大小；没有时显示已下载 KB/MB，进度条滚动）→ 解析站点/路线 → 解析点云 → 写入缓存。
  - /scene 里没有点云（`normalPosList`）时从地图取点云，多出这些阶段：下载地图（/downloadScene，同样显示百分比或 MB）→ 解压/解析地图 → 降采样点云（显示原始点数）；地图没变时显示「地图未变, 复用点云缓存」，跳过解析和降采样。
  - **点云缓存按内容判断**：`pointcloud_cache.json` 以地图文件内容的哈希为键；/downloadScene 下载的地图和上次内容相同时不覆盖 `maps/` 里的文件，直接复用缓存，只有内容变了才重新解析。已有 /scene 路线时解析地图只取点云、不再重算路线。
  - 服务端把加载做成后台任务（`/api/scene_geom?async=1` 启动，`/api/scene_job?id=` 查询进度），页面每 0.3 秒查询一次；同时触发的多次加载共用一个任务。所有加载入口都走这个任务。
- **失败提示**：
  - 手动加载、生成触发的加载失败：弹窗报错，站点区显示错误和「重试」按钮。
  - 页面打开时的自动加载失败：**不弹窗**，只在站点区显示错误。
  - 服务端把 `/scene` 返回 HTTP 非 2xx、网络错误、非 JSON 对象或解析异常都视为失败（不会当作 0 个站点成功）。
- **浏览器缓存**：页面和静态资源都带 `Cache-Control: no-store`，`app.js` 带版本号 `?v=<修改时间>`，部署后刷新即生效。
- **版本与编译日期**：左下角固定显示 `vX.Y.Z · YYYY-MM-DD HH:MM UTC`（`GET /api/version`；UTC 写入的 `BUILD_DATE`），侧栏展开/收起与地图铺满时均可见，不拦截点击。

### 站点朝向：旧缓存自动补齐
旧版 `scene_cache.json` 的站点没有 `dir`。启动恢复缓存时，如果所有站点都没有角度，后台会从本地 smap（设置里的 smapPath 或 `maps\` 下自动下载的地图）解析 `dir`/`ignoreDir`，补进缓存后写回，不需要重新下载地图。日志里记作 `dir_backfill`。本地没有 smap 时，重新加载一次场景即可（/scene 的 `dir` 字段单位是弧度）。

### 多个前置点的显示
一个站点有多条直连 LM 路线时，所有 LM 都是候选（例如 AP100 → LM101 / LM102）。
- 默认前置点（候选列表第一个，即最近的驶入 LM）在前置点信息行里加粗显示；其余候选用 `/` 接在后面，灰色。
- 地图上，默认候选的虚线较深，其他候选的虚线较淡。
- 至少有一个 LM 候选时，不再把非 LM 邻点（例如 AP-AP 连线上的 AP200）计入候选，避免 index、random 选到 AP。

### 站点池页的站点列表（只读）
列表只显示已经加入任一站点池的站点，不再列出场景里的全部站点。
- 列：站点、类型、坐标、前置点（默认前置点加粗，下面附候选列表）、所属池（彩色标签，一个站点可属于多个池）。
- 搜索框和类型过滤只在这些已选站点里筛选。
- 列表本身不能加站点。添加站点只有两种方式：
  - 在「地图」页点选站点；
  - 用「手动粘贴站点」。
- 要移除站点，点池里该站点标签上的 ×。
- 列表为空时会显示上面这几种添加方式的提示。

### 在 RDS 里取消的运单
- 轮询会一直跟踪 FAILED 运单（FAILED 不是终态，RDS 里还能恢复），直到它进入真正的终态。
- 终态包括：FINISHED、STOPPED、MANUAL_FINISHED、CANCELED/CANCELLED、WITHDRAWN、TERMINATED。进入终态后：
  - 时长冻结，记下结束时间；
  - 不再计入卡死；
  - 统计中按该状态计数；
  - 可以在状态过滤里勾选 CANCELED/STOPPED 筛出这类运单。
- 在 RDS 界面取消（撤销）的运单，RDS 会直接删掉记录：`/orderDetails/<id>` 返回 `{"code":50002,"msg":"order details is empty"}`。
  - 工具连续 3 次收到“查无此单”后，把该单记为 **CANCELED（RDS 已无此单）**，显示为紫色。结束时间取第一次查不到的时刻，日志里记 `order_change gone=true`。
  - 只有网络错误或超时时，不会这样判定。
  - 中途又能查到这单时，计数清零，按 RDS 返回的实际状态继续跟踪。
- 工具只用只读 GET 查询运单状态，不会对 RDS 发任何写操作。

### 逐块下发（block-by-block）
- 关闭时（默认）行为与以前完全相同：`POST /setOrder` 一次性带全部块，`complete: true`。
- 勾选后，每张运单独立跟踪（批量/自动派单的多张运单可同时进行）：
  1. `POST /setOrder`：只带第一个块，`complete: false`。
  2. 工具按「逐块轮询(秒)」间隔 `GET /orderDetails/<id>`，当最后一个已下发块的 `state` 为 `FINISHED` 时 `POST /addBlocks`，body `{"id": <运单ID>, "blocks": [下一块], "complete": false}`。
  3. 最后一块追加成功后立即 `POST /markComplete`，body `{"id": <运单ID>}`（封口）。
  - 成功判定：HTTP 200 且返回 `{"code": 0}`；addBlocks/markComplete 连续失败 5 次则停止。
- 停止条件：**只要运单未到终态就不会停止追加**。只有运单 `state` 为 `FINISHED` / `STOPPED`（在工具里取消 = RDS 终止 → STOPPED；以及 CANCELED/WITHDRAWN/TERMINATED/SKIPPED）才停止，原因写入日志（`inc_stopped`）。运单或块 `FAILED` / `Error`、`SUSPENDED`、`WAITING`、未知状态、orderDetails 请求失败/超时/查无此单、addBlocks 连续失败，都只记告警（`inc_warn`）暂停并继续轮询，恢复后继续追加（实测 RDS 会短暂报运单 FAILED 随后恢复 RUNNING）。
- 旧版本因 `order FAILED` / `order Error` / 查无此单 / addBlocks 多次失败而标记「已停止」的逐块运单（保存在 sent_orders.json），在启动或下一次轮询时自动恢复为追加中（日志 `inc_revived`），按 orderDetails 已有块续传，不重复追加。
- 测试订单页「状态」列后有 `逐块 k/N` 标签：蓝=追加中，绿 ✓=已全部追加并封口，橙=运单/块异常已暂停等待恢复（仍在轮询），红=运单终态（FINISHED/STOPPED）已停止（附原因，悬停看详情）。顶部状态行显示「逐块下发进行中 n 单」。
- 未封口的运单在 RDS 里所有块完成后状态是 `WAITING`（不是 FINISHED），封口后才 FINISHED。
- 工具重启：追加进度保存在 `sent_orders.json`，启动后自动恢复跟踪（日志 `inc_resume`，标签悬停显示「工具重启后已恢复跟踪」）。恢复时以 orderDetails 返回的块列表为准，已在 RDS 中的块不会重复追加。
- 日志事件：`inc_start`、`inc_add`、`inc_resync`、`inc_error`、`inc_done`、`inc_stopped`。
- 已对照官方 RDSCore HTTP API 文档（「运单」/「动作块」章节）核对：
  - `setOrder` 的 `complete`（bool，false=不封口，之后可 addBlocks）；`addBlocks` body `{id, blocks, complete?}`（`complete` 需 ≥0.1.8.22090102，本工具不用它封口）；`markComplete` body `{id}`（也支持 `{idList}`，本工具不用）。
  - 成功判定：HTTP 200 且 `code` 为 0 **或缺省**；错误码 40000/50000/50001/50002/50003（对已封口运单 addBlocks 返回 50003 "order is complete"）。
  - 运单状态：CREATED / WAITING / RUNNING / SUSPENDED / FINISHED / FAILED / STOPPED / Error / TOBEDISPATCHED；动作块状态另有 POSTING、MANUAL_FINISHED。
  - 逐块追加：前一块 `FINISHED` 或 `MANUAL_FINISHED`（手动完成）才追加下一块；**块**为 `FAILED` / `STOPPED` / `Error` 时只记录告警（标签变橙「块异常, 等待恢复」）并继续轮询，块恢复并 `FINISHED`/`MANUAL_FINISHED` 后继续追加；**运单** `FAILED` / `Error` 同样只暂停（标签橙「运单 FAILED, 暂停」）；只有运单 `state` 为终态 `FINISHED` / `STOPPED`（或取消）时才停止追加。SUSPENDED、WAITING、POSTING 及未知状态只等待，不停止。
  - 注意：RDS 默认允许 addBlocks 对不存在的运单 ID **自动创建运单**（参数 CreateNewOrderWhileAddBlocks），所以工具每次追加前都先用 orderDetails 确认运单仍存在；查无此单就停止，不再追加。

## M4 调度系统

本工具也可以对接 M4 调度服务器来代替 RDS。默认仍为 RDS，RDS 用户不受影响。

### 配置
1. 在"配置与派单 → 连接"中，把"调度系统"设为 `M4`，会出现"M4 连接"区域；上方「调度系统地址」即该 M4 的 `http://<m4-host>:<port>`（端口因现场而异）。M4 连接按**左侧服务器**分条保存（同一服务器内不再提供多配置切换）。
2. 为当前服务器填写字段（含地址）：
   - 场景：运单创建所在的 M4 场景。点"测试连接"后从下拉列表选择，选项显示为「场景名（ID）」（不可手输 ID）。
   - 认证：二选一——"应用 ID / 密钥"（程序客户端，由 M4 管理员在代理用户菜单中创建，请求头带 `xyy-app-id` / `xyy-app-key`）或"用户名 / 密码"（`POST /api/sign-in` 会话 cookie，401 后重新登录）。选哪种只显示对应输入框。
   - 应用 ID、应用密钥、用户名、密码（随所选认证方式显示）。
3. 点「保存」同时写入上方参数与当前服务器的 M4 连接（改动也会自动存）。
4. **动作模式**在「订单模板」每一步上选择（不再有模板右侧全局「步骤动作字段」）。`binTask` 发送 `rbkArgs: {"binTask": <动作>}`（不带普通参数）；`operation` 发送 `rbkArgs: {"operation": <动作>, ...参数}`。脚本步骤始终使用 `operation: "Script"`。存储中遗留的 `opMode` 仅作缺省回退，UI 不再编辑。

应用密钥和密码只保存在本地、已被 git 忽略的 `settings.json` 中。界面、`/api/settings` 和 `/api/m4` 中显示为 `******`，日志中不会出现。字段保持 `******` 不变即沿用已保存的值。也可以使用环境变量 `ODT_M4_APP_ID`、`ODT_M4_APP_KEY`、`ODT_M4_USER`、`ODT_M4_PASSWORD`、`ODT_M4_SCENE`，它们用于填补连接中为空的字段。

### 按步骤提示（模板步骤的 `args` / `opMode`）
- 步骤字段 `opMode`：`"binTask"` 或 `"operation"`（主入口；M4 与 RDS 通用）。
- 以下键由 M4 适配器读取，不会放进 `rbkArgs`：
  - `m4Mode`（旧）：`"binTask"` 或 `"operation"`，校验时迁移到 `opMode` 后可清理。
  - `m4BinTask`：代替动作名发送的库位任务名，例如 `"Load"`。
  - `forLoad` / `forUnload`：默认动作名含 "unload" 的步骤为 `forUnload: true`，含 "load" 的为 `forLoad: true`，其他步骤两者都为 false。可显式设置以覆盖。

### M4 适配器的映射
- RDS 运单 = M4 运单；RDS 动作块 = M4 步骤（步骤 `id` = 运单号 + 动作块后缀，与 RDS blockId 相同）；RDS `complete` = M4 `stepFixed`（封口）。
- 普通下发：`POST /api/fleet/orders/create`，带全部步骤，`stepFixed: true`。指定车辆、机器人组分别对应 `expectedRobotNames` / `expectedRobotGroups`，label(可选) 对应 `externalId`。
- 逐块下发：创建时只带第一个步骤且 `stepFixed: false`；上一个步骤 `Done` 后用 `POST /api/fleet/orders/add-steps` 追加下一个；最后用 `POST /api/fleet/orders/complete-order` 封口。
- 状态通过 `GET /api/fleet/orders/query-order-detail` 按"轮询间隔（秒）"和"逐块轮询（秒）"轮询，与 RDS 相同（不使用回调）。状态以本工具的 RDS 风格名称显示：

| M4 | 显示为 | 效果 |
|---|---|---|
| Done | FINISHED | 终态，停止追加 |
| Cancelled | STOPPED | 终态，停止追加 |
| 任何状态且 `fault: true` | FAILED | 仅暂停（警告），继续轮询和追加 |
| ToBeAllocated / Allocated / Executing | TOBEDISPATCHED / CREATED / RUNNING | 正常 |
| Pending | 未封口为 WAITING，否则 RUNNING | 正常 |
| Cancelling、Withdrawing、未知状态 | 原样大写显示 | 非终态，继续轮询 |

  查询出错（HTTP 错误、401/403、超时）以及 add-steps/complete-order 出错都只暂停，与 RDS 完全相同。只有 Done 和 Cancelled 才停止追加。
- 机器人：`GET /api/fleet/robots/all-all?sceneId=`。站点与地图：`GET /api/fleet/scenes/schema/{sceneId}`，使用 `structure.areas[].mergedMap`（点位、路径、库位，以及有则带上的点云 `normalPosList`），未知字段会被忽略。地图页加载全部点位（含 LM），前置点仍取通过路径相连的最近 `LM`；路线按 `className`/`curveType` 与控制点镶嵌；点云优先取 schema 的 `normalPosList`，没有时则按各区域 `groupsMap.*.mapFile` 走 `GET /api/fleet/scenes/{sceneId}/download/{mapFile}`（与 M4 界面下载地图同一 URL；`.smap` 解析/降采样/缓存与 RDS `/downloadScene` 相同），不是站点坐标。
- "取消选中订单"和"取消全部未完成测试订单"使用 `POST /api/fleet/orders/cancel {sceneId, orderId}`。

### 无真实 M4 时的测试
`python tools/fake_m4.py --port 18090` 启动一个使用模拟数据的 M4 模拟服务器（场景 `scene-1`，应用 ID/密钥 `mock-app`/`mock-key`，登录 `mockuser`/`mockpass`）。运单号含 `fault` 的会故障一段时间后恢复；含 `qerr` 的查询会失败一段时间；含 `xcancel` 的在第一个步骤完成后被 M4 取消。
地图「选择：」为下拉框，选项为**站点池名称**（点击地图站点加入对应池）。
地图页铺满视口（无页面滚动条），画布随窗口自动缩放。
