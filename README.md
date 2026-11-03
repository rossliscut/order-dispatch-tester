# Order Dispatch Tester

[中文说明 / Chinese](README.zh-CN.md)

> Detailed usage guide: [English](docs/USAGE.en.md) | [中文](docs/USAGE.zh.md) — **every feature change must update both language versions.**


A small, stdlib-only Python web tool for **stress / deadlock testing of AGV dispatch systems**.
It generates test orders from configurable **order templates**, sends them in throttled batches,
monitors every order and vehicle, and highlights orders that look stuck (possible deadlocks).

The first (and currently only) dispatcher adapter is **SEER RDS**. The core is dispatcher-neutral so
other systems (e.g. VDA 5050) can be added as adapters later.

## Features

- **Order templates**: an ordered list of steps; each step has a location source (named pool,
  pre-point of another step's station, or fixed station), an operation, args with variables,
  an optional `variableShape` and an enabled flag. Built-in `default` template = the classic
  five-block RDS deadlock order (pick-pre Wait → ForkLoad → Script → ForkUnload → ForkHeight).
- **Named station pools** (`start` / `end` by default, add any others), pool swap, per-station delete,
  pick from the station table or by clicking the map.
- **Generation strategies**: random without reuse (default, count = size of the first pool),
  round-robin, full cartesian product.
- **Template editor**: list / new / copy / delete / import / export (`templates/*.json`),
  add / remove / reorder (buttons or drag) / enable steps, per-step form or raw JSON mode,
  live preview of a sample order as the dispatcher will receive it.
- **Batches**: generate drafts, then send the selected ones with an interval and a max-open-orders limit;
  orders are grouped by batch with totals, filters, sorting, start / end / duration columns.
- **Stuck detection**: an order is "possibly stuck" when it has a vehicle and nothing changed for N seconds.
  `FAILED` is *not* terminal (RDS can resume), unassigned orders are not counted, vehicle movement
  > 5 cm or > 2° counts as a change.
- **Map** (routes and point cloud from the dispatcher scene / `/downloadScene`; no manual `.smap` upload), **robots** by group.
- **Chinese / English UI**, switchable (top-right), persisted; Chinese by default.

## Run

Python 3.8+; no third-party packages.

```sh
python run.py --port 5088 --rds http://<rds-host>:8088
# or
python -m order_tester --port 5088
```

Open <http://127.0.0.1:5088>. On Windows double-click `start_tester.bat` (runs `pythonw` in the
background, then opens the browser; set `PYW` to the full path of `pythonw.exe` if it is not on PATH).

Options: `--port`, `--host` (default 127.0.0.1), `--rds/--base` dispatcher URL, `--data DIR` (where
`settings.json`, `drafts.json`, `sent_orders.json`, `templates/`, `logs/`, `maps/` live; default = the
project folder, or env `ORDER_TESTER_DATA`), `--adapter` (default `rds`).

## Configure the RDS address

Either pass `--rds http://<rds-host>:8088`, or type it into **Config → Dispatcher URL** and click Save
(stored in `settings.json`). The tester only talks to RDS when you load the scene, send, cancel, or while
monitoring sent orders.

## Templates

Templates are JSON files in `<data>/templates/`. `default.json` is created on first start (from the
legacy `settings.json` if present, otherwise from the built-in). Example templates: `examples/templates/`.

```json
{"name": "my_template", "title": "...", "steps": [
  {"id": "s", "name": "Pick", "enabled": true,
   "location": {"type": "pool", "pool": "start"},
   "operation": "ForkLoad", "args": {"recfile": "plt/example.plt"},
   "vsOn": false, "variableShape": {"head": 1.5, "tail": 1.5}},
  {"id": "pre", "location": {"type": "pre", "step": "e"}, "operation": "Script",
   "args": {"script_name": "userpy/x.py", "script_args": {"locName": "{end}"}}},
  {"id": "e", "location": {"type": "pool", "pool": "end"}, "operation": "ForkUnload", "args": {}},
  {"id": "park", "enabled": false, "location": {"type": "fixed", "station": "PARK-1"}, "operation": "none", "args": {}}
]}
```

- `location.type`: `pool` (pick from the named pool via the strategy), `pre` (pre-point of the station of
  another step: manual override map first, then scene derivation AP→LM), `fixed` (a fixed station).
  `pool` / `fixed` may also set `target`: `station` (default) or `bin`. Bin does not store a bin name;
  when that station has several bins, `select` / `selArg` are the same criteria as a pre-point.
- Pool entries are station-name strings (a legacy `{"station","bin"}` is only a label). When a step goes
  to a bin, M4 writes the bin name resolved from **that station's** bins into the step `location`;
  pre-points and "no repeated station" still use the station. RDS keeps sending the station. A bin target
  is not the same thing as `opMode=binTask`. An old `location.bin="Loc-…"` is dropped on validate and the
  step stays on the station.
- `operation: "none"` = move only. Optional `blockSuffix` sets the RDS blockId suffix (default `-<id>`).
- Variables in args strings: `{start}`, `{end}`, `{<pool>}`, `{pickPre}`, `{dropPre}`, `{pre:<pool>}`,
  `{stationOf:<step id|stepN>}`, `{preOf:<step>}`, `{orderId}`. Unknown variables are an error.
- Pools are picked in step order; a station is not repeated in one order when "no repeated station" is on.

## Dispatcher adapter interface

`order_tester/adapters/base.py` defines `DispatcherAdapter`; `order_tester/adapters/rds.py` implements it
for RDS (`/scene`, `/downloadScene`, `/setOrder`, `/orderDetails/<id>`, `/robotsStatus`, `/terminate`).

| method | purpose |
|---|---|
| `build_payload(order)` | neutral order (from a template) → dispatcher JSON |
| `submit(payload)` | send one order → `(ok, error_text)` |
| `order_status(id)` | normalised `{state, vehicle, blockStates, ...times}` or `None` |
| `cancel(id)` | terminate one order |
| `robots()` | normalised robot list `{name, x, y, angle, order, orderState, ...}` |
| `scene()`, `parse_stations()`, `parse_groups()`, `extract_geom()`, `download_maps()`, `decode_map()` | optional scene / map support |
| `terminal_states` | states that stop polling (RDS: FAILED is **not** terminal) |

To add a dispatcher: subclass `DispatcherAdapter`, register it in `order_tester/adapters/__init__.py`
(`ADAPTERS`), start with `--adapter <name>` (or `"adapter"` in `settings.json`).

## Migration from rds_tester.py (v1)

Copy `settings.json`, `drafts.json`, `sent_orders.json` (and optionally `logs/`, `maps/`) into the data
folder and start. On first start:

- the old fixed form (start/end operation + args, Script, lift, pick-pre Wait, per-block variableShape)
  becomes `templates/default.json`, generating byte-identical setOrder JSON;
- `starts` / `ends` become `pools.start` / `pools.end`; `activeTemplate` is set; a backup
  `settings.json.bak-v1` is written; old keys are kept;
- drafts and sent orders get `picks` / `template` / `adapter` fields on load; FAILED orders that an older
  version had marked as ended are monitored again; legacy history batches are rebuilt from logs.

## Tests

```sh
python -m unittest -v
```

Includes a regression test that runs the original `build_order` / `Picker` / `make_draft`
(`tests/legacy_reference.py`) and the new template engine with the same seeds and inputs and requires
identical JSON (including key order), migration tests, template / strategy tests and an end-to-end test
against `tools/fake_rds.py` (a tiny fake RDS you can also run by hand: `python tools/fake_rds.py`).

UI strings live in `order_tester/i18n/{zh,en}.json` and are edited directly. `tools/i18n_src.py` is a legacy generator that is now outdated; it refuses to run without `--force` because running it would overwrite the current strings.

## License

MIT License - see [LICENSE](LICENSE). Copyright (c) 2026 Ross Li.
