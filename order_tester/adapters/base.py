# -*- coding: utf-8 -*-
"""Dispatcher adapter interface.

The core (order generation, batching, polling, stuck detection, UI) only talks to a
``DispatcherAdapter``. An adapter converts a *neutral order* (see templates.build_order) to the
dispatcher's payload and wraps the dispatcher's HTTP/MQTT API.

Neutral order::

    {"id": str, "template": str, "picks": {pool: station},
     "priority": int, "vehicle": str, "group": str, "label": str,
     "steps": [{"id", "name", "location", "operation", "args": {...},
                "suffix": "-s", "variableShape": {"head", "tail"} (optional, RDS),
                "keepFinalPathSpace": True (optional, M4)}]}

Normalised order status (``order_status``)::

    {"state": str|None, "vehicle": str, "blockStates": [raw block states],
     "blockStartTimes": [epoch s], "createTime", "receiveTime", "terminateTime", "finishTime": epoch s|None}

Normalised robot (``robots``)::

    {"name", "x", "y", "angle", "station", "order", "orderState" (may be None),
     "group", "dispatchable", "connected", "blocked", "battery"}
"""

class DispatcherAdapter(object):
    name = "base"
    #: states after which an order is no longer polled. NOTE for RDS: FAILED is *not* terminal.
    terminal_states = frozenset()
    #: True: the base URL follows the shared "base" field/setting (RDS). False: the adapter keeps its own (M4 profile).
    base_from_settings = True

    def __init__(self, base_url, log=None, opts=None):
        self.base = base_url
        self.log = log or (lambda kind, **kw: None)

    def configure(self, opts):
        """apply adapter-specific options (connection profile, auth ...). Default: nothing to configure."""

    # ---- orders
    def build_payload(self, order):
        """neutral order -> dispatcher payload (JSON-serialisable). Must be deterministic."""
        raise NotImplementedError
    def submit(self, payload):
        """send one order. returns (ok: bool, error_text: str|None)"""
        raise NotImplementedError
    def order_status(self, order_id, quiet=True, timeout=8):
        """normalised status dict, or None if the dispatcher did not answer with an order"""
        raise NotImplementedError
    def cancel(self, order_id):
        """terminate/cancel one order; returns the dispatcher's response (JSON or text)"""
        raise NotImplementedError

    # ---- incremental ("block-by-block") orders, optional
    supports_incremental = False
    def incremental_payload(self, payload, n):
        """payload of an open (not complete) order carrying only the first n blocks"""
        raise NotImplementedError
    def payload_blocks(self, payload):
        """list of block objects of a full payload (same order as executed)"""
        raise NotImplementedError
    def block_id(self, block): raise NotImplementedError
    def add_blocks(self, order_id, blocks, complete=False):
        """append blocks to an open order. returns (ok, error_text|None)"""
        raise NotImplementedError
    def mark_complete(self, order_id):
        """close an open order (no more blocks). returns (ok, error_text|None)"""
        raise NotImplementedError

    # ---- fleet
    def robots(self):
        """list of normalised robots, or None if unavailable"""
        raise NotImplementedError

    # ---- scene / map (optional)
    def scene(self, progress=None):
        """(status, raw_scene_or_None, text). The raw scene is opaque to the core.
        progress(stage, done=None, total=None) may be called with stage "request" / "download" (bytes)."""
        return None, None, "scene not supported by " + self.name
    def parse_stations(self, scene):
        """[{name, type, x, y, pre, preSrc, preCands, bins}] - 'pre' is the derived pre-point"""
        return []
    def parse_groups(self, scene):
        """[{name, robots: [id]}]"""
        return []
    def extract_geom(self, scene, points_only=False):
        """(curves [{n, c, p: [[x, y]...]}], points [(x, y)]); points_only skips curves"""
        return [], []
    def download_maps(self, timeout=120, progress=None):
        """(status, bytes) of a zip with map files, or (None, b'') if unsupported"""
        return None, b""
    def decode_map(self, raw):
        """map file bytes -> list of JSON objects understood by extract_geom"""
        return []
    def raw_get(self, path):
        """read-only debugging proxy: (status, json_or_None, text)"""
        return None, None, "unsupported"
