#!/usr/bin/env python3
"""
rtlmap — Interactive RTL Block Diagram Viewer
=============================================

Usage:
    python rtlmap.py <file.v|dir> [more ...]  [--port 7474] [--no-browser]
    python rtlmap.py examples/                 # scan a whole directory
    python rtlmap.py cpu.v alu.v regfile.v     # explicit files
    python rtlmap.py *.v --port 8080           # glob (shell-expanded)

When a directory is given, all .v/.sv files inside are parsed and the top
module is found automatically. Referenced modules not in the given set are
auto-discovered in the same directories.

Press Ctrl+C to stop the server.
"""

import argparse
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT   = Path(__file__).parent
STATIC = ROOT / "static"

try:
    from rtl_engine import RTLEngine, PATTERN_LIBRARY
except ImportError as e:
    print(f"Error: cannot import rtl_engine.py — {e}")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# HTTP SERVER
# ─────────────────────────────────────────────────────────────────────────────

DESIGN_DATA = {}
MIME = {
    ".html": "text/html",
    ".js":   "application/javascript",
    ".css":  "text/css",
    ".json": "application/json",
    ".svg":  "image/svg+xml",
    ".png":  "image/png",
    ".ico":  "image/x-icon",
}


class RTLHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # suppress routine request logs

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        params = parse_qs(parsed.query)

        # ── API ───────────────────────────────────────────────────────────
        if path == "/api/design":
            self._json(DESIGN_DATA)

        elif path.startswith("/api/module/"):
            mid = path.split("/")[-1]
            mods = DESIGN_DATA.get("modules", {})
            if mid in mods:
                self._json(mods[mid])
            else:
                self._json({"error": f"Module '{mid}' not found"}, 404)

        elif path == "/api/patterns":
            self._json({k: {
                "label": v["label"],
                "color": v["color"],
                "icon":  v["icon"],
                "composition":      v.get("composition", []),
                "gate_composition": v.get("gate_composition", []),
            } for k, v in PATTERN_LIBRARY.items()})

        elif path == "/api/search":
            q = params.get("q", [""])[0].lower().strip()
            results = self._search(q) if q else []
            self._json({"query": q, "results": results})

        elif path == "/api/hierarchy":
            self._json(self._hierarchy())

        # ── Static ────────────────────────────────────────────────────────
        elif path in ("/", "/index.html"):
            self._file(STATIC / "index.html")

        else:
            fpath = STATIC / path.lstrip("/")
            if fpath.exists():
                self._file(fpath)
            else:
                self._text("404 Not Found", 404)

    def _search(self, q):
        """Full-text search across all blocks in all modules."""
        results = []
        for mod_name, mod in DESIGN_DATA.get("modules", {}).items():
            for b in mod.get("blocks", []):
                label    = b.get("label", "").lower()
                sublabel = b.get("sublabel", "").lower()
                btype    = b.get("type", "").lower()
                port_names = " ".join(
                    (p["name"] if isinstance(p, dict) else p)
                    for p in b.get("inputs", []) + b.get("outputs", [])
                ).lower()
                if q in label or q in sublabel or q in btype or q in port_names:
                    results.append({
                        "module": mod_name,
                        "block_id": b["id"],
                        "label": b["label"],
                        "sublabel": b.get("sublabel", ""),
                        "type": b.get("type", ""),
                        "color": b.get("color", "#888"),
                    })
        return results[:50]

    def _hierarchy(self):
        """Return a tree structure for the module hierarchy."""
        modules = DESIGN_DATA.get("modules", {})
        top = DESIGN_DATA.get("top_module", "")

        def build_node(name, visited=None):
            if visited is None:
                visited = set()
            if name in visited:
                return {"name": name, "children": [], "circular": True}
            visited = visited | {name}
            mod = modules.get(name, {})
            children = []
            for b in mod.get("blocks", []):
                if b.get("source") == "instance" and b.get("drilldown_module"):
                    child_name = b["drilldown_module"]
                    children.append(build_node(child_name, visited))
            return {
                "name": name,
                "is_top": mod.get("is_top", False),
                "is_orphan": mod.get("is_orphan", False),
                "file": mod.get("file", ""),
                "block_count": len(mod.get("blocks", [])),
                "children": children,
            }

        return {
            "top": build_node(top) if top else {},
            "orphans": [
                {"name": n, "file": modules[n].get("file",""), "block_count": len(modules[n].get("blocks",[]))}
                for n in DESIGN_DATA.get("orphan_modules", [])
                if n in modules
            ],
        }

    def _json(self, data, code=200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, fpath):
        try:
            with open(fpath, "rb") as f:
                body = f.read()
            mime = MIME.get(Path(fpath).suffix.lower(), "application/octet-stream")
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self._text(f"Not found: {fpath}", 404)

    def _text(self, text, code=200):
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


def start_server(port, open_browser):
    server = HTTPServer(("127.0.0.1", port), RTLHandler)
    url = f"http://localhost:{port}"
    w = max(len(url) + 8, 44)
    print(f"\n  ┌{'─'*w}┐")
    print(f"  │  RTL Viewer  →  {url}{' '*(w-len(url)-18)}│")
    print(f"  └{'─'*w}┘")
    print(f"  Press Ctrl+C to stop.\n")
    if open_browser:
        threading.Timer(0.6, webbrowser.open, args=[url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
        server.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

BANNER = r"""
  ██████╗ ████████╗██╗     ███╗   ███╗ █████╗ ██████╗
  ██╔══██╗╚══██╔══╝██║     ████╗ ████║██╔══██╗██╔══██╗
  ██████╔╝   ██║   ██║     ██╔████╔██║███████║██████╔╝
  ██╔══██╗   ██║   ██║     ██║╚██╔╝██║██╔══██║██╔═══╝
  ██║  ██║   ██║   ███████╗██║ ╚═╝ ██║██║  ██║██║
  ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝
  Interactive RTL Block Diagram Viewer
"""


def collect_files(paths, recursive):
    """Resolve a mixed list of files, directories, and globs to .v/.sv files."""
    result = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            # directory: scan for RTL source files
            pattern = "**/*.v" if recursive else "*.v"
            found = list(pp.glob(pattern)) + list(pp.glob(pattern.replace(".v", ".sv")))
            result.extend(found)
            if not found:
                print(f"  Warning: no .v/.sv files found in {pp}")
        elif pp.is_file():
            result.append(pp)
        else:
            # Try glob expansion (in case shell didn't expand it)
            import glob as glob_mod
            matched = glob_mod.glob(str(pp))
            if matched:
                result.extend(Path(m) for m in matched)
            else:
                print(f"  Warning: not found: {p}")
    return [str(f.resolve()) for f in result]


def print_hierarchy(design_data):
    """Pretty-print the discovered module hierarchy."""
    modules = design_data.get("modules", {})
    top = design_data.get("top_module", "")
    orphans = design_data.get("orphan_modules", [])

    def _print_tree(name, visited, prefix="", is_last=True):
        if name in visited:
            print(f"  {prefix}{'└─' if is_last else '├─'} {name} (↺ circular)")
            return
        visited = visited | {name}
        mod = modules.get(name, {})
        blocks = mod.get("blocks", [])
        nb = len(blocks)
        tag = " [TOP]" if mod.get("is_top") else ""
        file_tag = f"  ← {mod.get('file','')}" if mod.get("file") else ""
        connector = '└─' if is_last else '├─'
        print(f"  {prefix}{connector} {name}{tag}  ({nb} block{'s' if nb!=1 else ''}){file_tag}")
        children = [b for b in blocks if b.get("source") == "instance" and b.get("drilldown_module")]
        for i, child_block in enumerate(children):
            child_name = child_block["drilldown_module"]
            child_is_last = (i == len(children) - 1)
            child_prefix = prefix + ("   " if is_last else "│  ")
            _print_tree(child_name, visited, child_prefix, child_is_last)

    if top:
        print("\n  Hierarchy:")
        _print_tree(top, set())

    if orphans:
        print(f"\n  Standalone (not instantiated by anyone):")
        for o in orphans:
            mod = modules.get(o, {})
            nb = len(mod.get("blocks", []))
            print(f"    • {o}  ({nb} block{'s' if nb!=1 else ''})  ← {mod.get('file','')}")
    print()


def main():
    ap = argparse.ArgumentParser(
        description="Interactive hierarchical RTL block diagram viewer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rtlview.py examples/             # whole directory
  python rtlview.py design.v              # single file
  python rtlview.py cpu.v alu.v regfile.v # multiple files
  python rtlview.py *.v --port 8080       # glob + custom port
  python rtlview.py src/ --no-recursive   # top-level dir only
  python rtlview.py design.v --dump-json out.json
        """
    )
    ap.add_argument("paths", nargs="+", metavar="FILE|DIR",
                    help="Verilog/SystemVerilog file(s) or directory/ies")
    ap.add_argument("--port", "-p", type=int, default=7474,
                    help="Local port (default: 7474)")
    ap.add_argument("--no-browser", action="store_true",
                    help="Don't open browser automatically")
    ap.add_argument("--no-recursive", action="store_true",
                    help="Don't recurse into subdirectories when scanning")
    ap.add_argument("--include-tb", action="store_true",
                    help="Include testbench files (tb_*, *_tb, *_test)")
    ap.add_argument("--top", metavar="MODULE",
                    help="Override top module name")
    ap.add_argument("--dump-json", metavar="OUT.json",
                    help="Write design JSON to file and exit")

    args = ap.parse_args()
    print(BANNER)

    recursive = not args.no_recursive
    files = collect_files(args.paths, recursive)

    if not files:
        print("  Error: no valid input files found.")
        sys.exit(1)

    # Filter testbenches unless asked to include them
    if not args.include_tb:
        tb_kw = {"tb_", "_tb", "_test", "testbench", "_bench", "_sim"}
        before = len(files)
        files = [f for f in files if not any(kw in Path(f).stem.lower() for kw in tb_kw)]
        removed = before - len(files)
        if removed:
            print(f"  Skipped {removed} testbench file(s) (use --include-tb to keep)")

    # Deduplicate
    seen_paths = set()
    unique_files = []
    for f in files:
        if f not in seen_paths:
            seen_paths.add(f)
            unique_files.append(f)
    files = unique_files

    print(f"  Input: {len(files)} file(s)")
    if len(files) <= 10:
        for f in files:
            print(f"    {Path(f).name}")

    # ── Analyze ────────────────────────────────────────────────────────────
    global DESIGN_DATA
    engine = RTLEngine()

    # Collect all parent directories as extra search paths
    extra_dirs = list({str(Path(f).parent) for f in files})
    DESIGN_DATA = engine.analyze(files, extra_search_dirs=extra_dirs)

    # Override top module if requested
    if args.top:
        if args.top in DESIGN_DATA.get("modules", {}):
            DESIGN_DATA["top_module"] = args.top
            print(f"  Top module overridden: {args.top}")
        else:
            print(f"  Warning: --top '{args.top}' not found in parsed modules")

    print_hierarchy(DESIGN_DATA)

    # ── Optional JSON dump ────────────────────────────────────────────────
    if args.dump_json:
        with open(args.dump_json, "w") as jf:
            json.dump(DESIGN_DATA, jf, indent=2)
        print(f"  JSON written to {args.dump_json}")
        return

    # ── Start server ──────────────────────────────────────────────────────
    start_server(args.port, not args.no_browser)


if __name__ == "__main__":
    main()
