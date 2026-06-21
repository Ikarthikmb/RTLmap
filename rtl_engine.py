"""
rtl_engine.py — RTL parsing, pattern matching, and graph building.

No external dependencies. Handles Verilog 2001 and most SystemVerilog.
"""

import re
import os
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# PATTERN LIBRARY  (warm-matte colour palette — no blue, pink, or purple)
# ─────────────────────────────────────────────────────────────────────────────
PATTERN_LIBRARY = {
    "multiplier": {
        "label": "Multiplier",
        "operators": ["*"],
        "name_hints": ["mul", "mult", "multiply"],
        "sensitivity": None,
        "color": "#b87c20",   # amber
        "icon": "✕",
        "composition": [
            {"id": "_pp",  "label": "Partial Products",          "type": "partial_product", "color": "#9a6618", "icon": "⊗"},
            {"id": "_wt",  "label": "Wallace Tree / Adder Tree", "type": "adder_tree",      "color": "#8a5a14", "icon": "⊕"},
            {"id": "_cpa", "label": "Carry-Propagate Adder",     "type": "adder",           "color": "#7a4e10", "icon": "+"},
        ],
        "gate_composition": [
            {"id": "_and", "label": "AND (partial products)", "type": "gate_and", "color": "#6e4208"},
            {"id": "_ha",  "label": "Half Adder",             "type": "gate_ha",  "color": "#7a4e10"},
            {"id": "_fa",  "label": "Full Adder",             "type": "gate_fa",  "color": "#8a5a14"},
        ],
    },
    "adder": {
        "label": "Adder / Subtractor",
        "operators": ["+", "-"],
        "name_hints": ["add", "adder", "sum", "sub", "subtractor"],
        "sensitivity": None,
        "color": "#507a38",   # sage green
        "icon": "+",
        "composition": [
            {"id": "_ha", "label": "Half Adder (bit 0)",     "type": "half_adder", "color": "#427030", "icon": "½+"},
            {"id": "_fa", "label": "Full Adders (bit 1..N)", "type": "full_adder", "color": "#365e26", "icon": "FA"},
        ],
        "gate_composition": [
            {"id": "_xor", "label": "XOR gates (sum)",   "type": "gate_xor", "color": "#2a4e1e"},
            {"id": "_and", "label": "AND gates (carry)",  "type": "gate_and", "color": "#1e3e14"},
            {"id": "_or",  "label": "OR gates (carry)",   "type": "gate_or",  "color": "#162e0e"},
        ],
    },
    "mux": {
        "label": "Multiplexer",
        "operators": ["?", "case"],
        "name_hints": ["mux", "sel", "select"],
        "sensitivity": None,
        "color": "#847840",   # warm tan / khaki
        "icon": "⇒",
        "composition": [
            {"id": "_sel",  "label": "Select Logic", "type": "decoder",  "color": "#726830", "icon": "D"},
            {"id": "_pass", "label": "Pass Gates",   "type": "tristate", "color": "#625a26", "icon": "Z"},
        ],
        "gate_composition": [
            {"id": "_and", "label": "AND (select)", "type": "gate_and", "color": "#524c1e"},
            {"id": "_or",  "label": "OR (merge)",   "type": "gate_or",  "color": "#443e18"},
            {"id": "_not", "label": "NOT (invert)", "type": "gate_not", "color": "#363212"},
        ],
    },
    "register": {
        "label": "Register / Flip-Flop",
        "operators": ["<="],
        "name_hints": ["reg", "ff", "flop", "latch", "dff"],
        "sensitivity": "posedge|negedge",
        "color": "#5e7060",   # sage gray-green (clearly not blue)
        "icon": "D",
        "composition": [
            {"id": "_d",   "label": "D Flip-Flop",  "type": "dff",      "color": "#4e6050", "icon": "D"},
            {"id": "_rst", "label": "Reset Logic",  "type": "mux",      "color": "#3e5042", "icon": "R"},
            {"id": "_en",  "label": "Enable Logic", "type": "gate_and", "color": "#2e3e32", "icon": "E"},
        ],
        "gate_composition": [
            {"id": "_nand1", "label": "NAND (master)", "type": "gate_nand", "color": "#283428"},
            {"id": "_nand2", "label": "NAND (slave)",  "type": "gate_nand", "color": "#1e2a1e"},
        ],
    },
    "counter": {
        "label": "Counter",
        "operators": ["+", "<="],
        "name_hints": ["count", "cnt", "counter", "ctr"],
        "sensitivity": "posedge|negedge",
        "color": "#387860",   # teal-green (more green than teal)
        "icon": "#",
        "composition": [
            {"id": "_reg", "label": "Count Register", "type": "register",   "color": "#2e6850", "icon": "D"},
            {"id": "_inc", "label": "Incrementer",    "type": "adder",      "color": "#507838", "icon": "+"},
            {"id": "_cmp", "label": "Comparator",     "type": "comparator", "color": "#786020", "icon": "="},
        ],
        "gate_composition": [
            {"id": "_fa",  "label": "Full Adders",  "type": "gate_fa",  "color": "#285840"},
            {"id": "_dff", "label": "D Flip-Flops", "type": "gate_dff", "color": "#1e4830"},
        ],
    },
    "comparator": {
        "label": "Comparator",
        "operators": ["==", "!=", ">", "<", ">=", "<="],
        "name_hints": ["cmp", "compare", "eq", "neq", "gt", "lt"],
        "sensitivity": None,
        "color": "#808028",   # khaki-olive
        "icon": "=",
        "composition": [
            {"id": "_xnor", "label": "XNOR (equality)", "type": "gate_xnor", "color": "#6a6820", "icon": "⊙"},
            {"id": "_and",  "label": "AND reduction",   "type": "gate_and",  "color": "#585816", "icon": "&"},
        ],
        "gate_composition": [
            {"id": "_xnor", "label": "XNOR gates", "type": "gate_xnor", "color": "#6a6820"},
            {"id": "_and",  "label": "AND gates",  "type": "gate_and",  "color": "#585816"},
        ],
    },
    "state_machine": {
        "label": "State Machine (FSM)",
        "operators": ["case", "<="],
        "name_hints": ["state", "fsm", "sm", "current_state", "next_state"],
        "sensitivity": "posedge|negedge",
        "color": "#983228",   # brick red
        "icon": "◉",
        "composition": [
            {"id": "_sreg",   "label": "State Register",   "type": "register",      "color": "#803020", "icon": "D"},
            {"id": "_nextst", "label": "Next-State Logic", "type": "combinational", "color": "#682818", "icon": "→"},
            {"id": "_out",    "label": "Output Logic",     "type": "combinational", "color": "#501e10", "icon": "⇒"},
        ],
        "gate_composition": [
            {"id": "_dff",  "label": "State FFs",   "type": "gate_dff", "color": "#803020"},
            {"id": "_comb", "label": "Comb. Logic", "type": "gate_mix", "color": "#682818"},
        ],
    },
    "shift": {
        "label": "Shifter / Barrel",
        "operators": ["<<", ">>", "<<<", ">>>"],
        "name_hints": ["shift", "barrel", "shl", "shr", "rotate"],
        "sensitivity": None,
        "color": "#805a30",   # warm brown
        "icon": "≫",
        "composition": [
            {"id": "_mux0", "label": "Stage 0 MUX (×1)", "type": "mux", "color": "#6e4c28", "icon": "⇒"},
            {"id": "_mux1", "label": "Stage 1 MUX (×2)", "type": "mux", "color": "#5c4020", "icon": "⇒"},
            {"id": "_mux2", "label": "Stage 2 MUX (×4)", "type": "mux", "color": "#4a3418", "icon": "⇒"},
        ],
        "gate_composition": [
            {"id": "_and", "label": "AND (mask)", "type": "gate_and", "color": "#3a2810"},
            {"id": "_or",  "label": "OR (merge)", "type": "gate_or",  "color": "#2a1e0a"},
        ],
    },
    "memory": {
        "label": "Memory / RAM / ROM",
        "operators": ["["],
        "name_hints": ["mem", "ram", "rom", "sram", "fifo", "bram", "cache",
                       "regfile", "reg_file", "rfile", "dpram"],
        "sensitivity": "posedge|negedge",
        "color": "#688040",   # olive green
        "icon": "▦",
        "composition": [
            {"id": "_arr",  "label": "Storage Array",    "type": "array",   "color": "#587034", "icon": "▦"},
            {"id": "_rdec", "label": "Row Decoder",      "type": "decoder", "color": "#486028", "icon": "D"},
            {"id": "_sa",   "label": "Sense Amp / MUX", "type": "mux",     "color": "#384c20", "icon": "⇒"},
        ],
        "gate_composition": [
            {"id": "_bit", "label": "Bit Cells",     "type": "gate_ff",  "color": "#304018"},
            {"id": "_dec", "label": "Decoder gates", "type": "gate_and", "color": "#243010"},
        ],
    },
    "alu": {
        "label": "ALU",
        "operators": ["+", "-", "&", "|", "^", "~", "<", ">", "=="],
        "name_hints": ["alu", "arith", "logic_unit"],
        "sensitivity": None,
        "color": "#707e38",   # olive yellow-green
        "icon": "∑",
        "composition": [
            {"id": "_add", "label": "Adder/Subtractor", "type": "adder",         "color": "#507838", "icon": "+"},
            {"id": "_log", "label": "Logic Unit",       "type": "combinational", "color": "#686830", "icon": "&"},
            {"id": "_cmp", "label": "Comparator",       "type": "comparator",    "color": "#787028", "icon": "="},
            {"id": "_sel", "label": "Output MUX",       "type": "mux",           "color": "#7a6030", "icon": "⇒"},
        ],
        "gate_composition": [
            {"id": "_fa",  "label": "Full Adders", "type": "gate_fa",  "color": "#3e5828"},
            {"id": "_xor", "label": "XOR (logic)", "type": "gate_xor", "color": "#545c20"},
            {"id": "_and", "label": "AND (logic)", "type": "gate_and", "color": "#445018"},
        ],
    },
    "fifo": {
        "label": "FIFO",
        "operators": ["<=", "["],
        "name_hints": ["fifo", "queue", "buffer"],
        "sensitivity": "posedge|negedge",
        "color": "#906030",   # amber-brown
        "icon": "⇌",
        "composition": [
            {"id": "_mem",  "label": "Storage Buffer",   "type": "memory",     "color": "#688040", "icon": "▦"},
            {"id": "_wptr", "label": "Write Pointer",    "type": "counter",    "color": "#387860", "icon": "#"},
            {"id": "_rptr", "label": "Read Pointer",     "type": "counter",    "color": "#387860", "icon": "#"},
            {"id": "_ctl",  "label": "Full/Empty Logic", "type": "comparator", "color": "#808028", "icon": "="},
        ],
        "gate_composition": [
            {"id": "_dff", "label": "Flip-Flops (ptrs)", "type": "gate_dff", "color": "#3a5028"},
            {"id": "_bit", "label": "Bit cells (data)",  "type": "gate_ff",  "color": "#4a3a18"},
        ],
    },
    "combinational": {
        "label": "Combinational Logic",
        "operators": ["&", "|", "^", "~"],
        "name_hints": [],
        "sensitivity": None,
        "color": "#5e5c54",   # warm gray
        "icon": "∧",
        "composition": [
            {"id": "_log", "label": "Logic Gates", "type": "gate_mix", "color": "#484644", "icon": "∧"},
        ],
        "gate_composition": [
            {"id": "_and", "label": "AND gates", "type": "gate_and", "color": "#3c3a38"},
            {"id": "_or",  "label": "OR gates",  "type": "gate_or",  "color": "#302e2c"},
            {"id": "_xor", "label": "XOR gates", "type": "gate_xor", "color": "#242220"},
        ],
    },
}

# Priority order for pattern matching (more specific first)
PATTERN_PRIORITY = [
    "fifo", "state_machine", "alu", "multiplier", "counter",
    "memory", "adder", "comparator", "shift", "mux",
    "register", "combinational",
]


# ─────────────────────────────────────────────────────────────────────────────
# VERILOG PARSER
# ─────────────────────────────────────────────────────────────────────────────

class VerilogParser:
    """
    Parses Verilog 2001 / SystemVerilog files without external dependencies.
    Extracts module structure, ports, always blocks, assign statements,
    and module instantiations.
    """

    def parse_files(self, file_paths):
        """
        Two-pass cross-file parse:
          Pass 1 — collect ALL module names across every file.
          Pass 2 — parse each file with the full cross-file name set, so
                   inter-file instantiations are recognised correctly.
        """
        cleaned = {}
        for fp in file_paths:
            try:
                with open(fp, "r", errors="replace") as f:
                    src = f.read()
                src = self._strip_comments(src)
                src = self._normalize_whitespace(src)
                cleaned[fp] = src
            except Exception as e:
                print(f"  Warning: could not read {fp}: {e}")

        known_names = set()
        for src in cleaned.values():
            for m in re.finditer(r"\bmodule\s+(\w+)", src):
                known_names.add(m.group(1))

        all_modules = []
        for fp, src in cleaned.items():
            try:
                modules = self._extract_modules_with_names(src, fp, known_names)
                all_modules.extend(modules)
            except Exception as e:
                print(f"  Warning: could not parse {fp}: {e}")
        return all_modules

    def _extract_modules_with_names(self, src, filepath, known_names):
        """Parse all modules in `src`, using `known_names` for instance detection."""
        spans = []
        for ms in re.finditer(r"\bmodule\s+(\w+)", src):
            name = ms.group(1)
            start = ms.start()
            end_m = re.search(r"\bendmodule\b", src[start:])
            if not end_m:
                continue
            spans.append((name, src[start : start + end_m.end()]))

        return [
            self._parse_module(name, body, filepath, known_names)
            for name, body in spans
        ]

    # ── Text pre-processing ───────────────────────────────────────────────

    def _strip_comments(self, text):
        text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
        text = re.sub(r"//[^\n]*", "", text)
        return text

    def _normalize_whitespace(self, text):
        return re.sub(r"[ \t]+", " ", text)

    # ── Module internals ─────────────────────────────────────────────────

    def _parse_module(self, name, body, filepath, known_module_names=None):
        # Count lines in body for stats
        line_count = body.count('\n')
        info = {
            "name": name,
            "file": str(Path(filepath).name),
            "filepath": str(filepath),
            "line_count": line_count,
            "ports": self._extract_ports(body),
            "params": self._extract_params(body),
            "signals": self._extract_signals(body),
            "always_blocks": self._extract_always_blocks(body),
            "assign_blocks": self._extract_assigns(body),
            "instances": self._extract_instances(body, name, known_module_names or set()),
        }
        return info

    def _extract_ports(self, body):
        ports = []
        seen = set()
        for m in re.finditer(
            r"\b(input|output|inout)\s+"
            r"(?:wire|reg|logic|signed|unsigned)?\s*"
            r"(?:\[([^\]]+)\])?\s*"
            r"(\w+(?:\s*,\s*\w+)*)",
            body,
        ):
            direction = m.group(1)
            width = m.group(2) or "0"
            names_raw = m.group(3)
            for pname in re.split(r"\s*,\s*", names_raw.strip()):
                pname = pname.strip()
                if pname and pname not in seen:
                    seen.add(pname)
                    ports.append({"name": pname, "dir": direction, "width": width})
        return ports

    def _extract_params(self, body):
        params = []
        for m in re.finditer(
            r"\bparameter\s+(?:\w+\s+)?(\w+)\s*=\s*([^,;)]+)", body
        ):
            params.append({"name": m.group(1), "value": m.group(2).strip()})
        return params

    def _extract_signals(self, body):
        signals = []
        seen = set()
        for m in re.finditer(
            r"\b(wire|reg|logic)\s+"
            r"(?:signed|unsigned)?\s*"
            r"(?:\[([^\]]+)\])?\s*"
            r"(\w+(?:\s*,\s*\w+)*)",
            body,
        ):
            kind = m.group(1)
            width = m.group(2) or "0"
            for sname in re.split(r"\s*,\s*", m.group(3).strip()):
                sname = sname.strip()
                if sname and sname not in seen:
                    seen.add(sname)
                    signals.append({"name": sname, "kind": kind, "width": width})
        return signals

    def _extract_always_blocks(self, body):
        blocks = []
        idx = 0
        for m in re.finditer(r"\balways(?:_ff|_comb|_latch)?\b", body):
            sens = ""
            pos = m.end()
            sens_m = re.match(r"\s*@\s*(\([^)]*\)|\*)", body[pos:])
            if sens_m:
                sens = sens_m.group(1).strip("() ")
                pos += sens_m.end()

            block_text = self._extract_block(body, pos)
            ops = self._scan_operators(block_text)
            signal_writes = self._extract_lhs_signals(block_text)
            signal_reads = self._extract_rhs_signals(block_text)
            has_case = bool(re.search(r"\bcase[xz]?\s*\(", block_text))
            has_if = bool(re.search(r"\bif\b", block_text))

            blocks.append({
                "id": f"always_{idx}",
                "sensitivity": sens,
                "text_snippet": block_text[:200].strip(),
                "operators": ops,
                "writes": signal_writes[:8],
                "reads": signal_reads[:8],
                "has_case": has_case,
                "has_if": has_if,
            })
            idx += 1
        return blocks

    def _extract_assigns(self, body):
        assigns = []
        for i, m in enumerate(
            re.finditer(r"\bassign\s+(\w+(?:\[[^\]]*\])?)\s*=\s*([^;]+);", body)
        ):
            lhs = m.group(1)
            rhs = m.group(2)
            ops = self._scan_operators(rhs)
            assigns.append({
                "id": f"assign_{i}",
                "lhs": lhs,
                "rhs": rhs.strip()[:100],
                "operators": ops,
            })
        return assigns

    def _skip_balanced(self, text, start, open_ch='(', close_ch=')'):
        depth = 0
        i = start
        while i < len(text):
            if text[i] == open_ch:
                depth += 1
            elif text[i] == close_ch:
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        return i

    def _extract_instances(self, body, current_module, known_module_names):
        """
        Only search for names that are in known_module_names — zero false positives.
        Returns list of {module, instance, port_connections}.
        """
        instances = []
        seen = set()

        for mod_name in known_module_names:
            if mod_name == current_module:
                continue

            for m in re.finditer(r'\b' + re.escape(mod_name) + r'\b', body):
                pos = m.end()

                ws = re.match(r'\s*', body[pos:])
                pos += ws.end() if ws else 0

                # Optional parameter block  #( ... )
                if pos < len(body) and body[pos] == '#':
                    pos += 1
                    ws2 = re.match(r'\s*', body[pos:])
                    pos += ws2.end() if ws2 else 0
                    if pos < len(body) and body[pos] == '(':
                        pos = self._skip_balanced(body, pos)

                ws3 = re.match(r'\s*', body[pos:])
                pos += ws3.end() if ws3 else 0

                inst_m = re.match(r'([A-Za-z_]\w*)\s*\(', body[pos:])
                if not inst_m:
                    continue

                inst_name = inst_m.group(1)
                _kw = {'begin','end','if','else','case','always','assign','wire',
                       'reg','logic','input','output','inout','parameter','module'}
                if inst_name in _kw:
                    continue

                key = (mod_name, inst_name)
                if key not in seen:
                    seen.add(key)
                    # Extract port connections  .portname(signal)
                    paren_start = pos + inst_m.end() - 1
                    port_block = body[paren_start : paren_start + 2000]
                    end_paren = self._skip_balanced(port_block, 0)
                    conn_text = port_block[:end_paren]
                    port_conns = {}
                    for pm in re.finditer(r'\.(\w+)\s*\(\s*(\w+(?:\[[^\]]*\])?)\s*\)', conn_text):
                        port_conns[pm.group(1)] = pm.group(2)

                    instances.append({
                        "module": mod_name,
                        "instance": inst_name,
                        "port_connections": port_conns,
                    })

        return instances

    # ── Helpers ───────────────────────────────────────────────────────────

    def _extract_block(self, text, start):
        rest = text[start:]
        bm = re.match(r"\s*begin\b", rest)
        if bm:
            depth = 1
            pos = bm.end()
            while pos < len(rest) and depth > 0:
                bkw = re.match(r"\s*\b(begin|end)\b", rest[pos:])
                if bkw:
                    if bkw.group(1) == "begin":
                        depth += 1
                    else:
                        depth -= 1
                    pos += bkw.end()
                else:
                    pos += 1
            return rest[:pos]
        else:
            semi = rest.find(";")
            if semi >= 0:
                return rest[:semi + 1]
            return rest[:100]

    # Ordered longest-to-shortest to avoid substring matches
    _OP_PATTERNS = [
        (re.compile(r'<<<'),               "arith_shift_left"),
        (re.compile(r'>>>'),               "arith_shift_right"),
        (re.compile(r'<<'),                "shift_left"),
        (re.compile(r'>>'),                "shift_right"),
        (re.compile(r'=='),                "equal"),
        (re.compile(r'!='),                "not_equal"),
        (re.compile(r'<='),                "nbassign"),
        (re.compile(r'>='),                "gte"),
        (re.compile(r'\*'),                "multiply"),
        (re.compile(r'\+'),                "add"),
        (re.compile(r'-'),                 "subtract"),
        (re.compile(r'/'),                 "divide"),
        (re.compile(r'%'),                 "modulo"),
        (re.compile(r'&(?!&)'),            "and"),
        (re.compile(r'\|(?!\|)'),          "or"),
        (re.compile(r'\^'),                "xor"),
        (re.compile(r'~'),                 "not"),
        (re.compile(r'\?'),                "ternary"),
        (re.compile(r'(?<![<>!])>(?!=)'), "gt"),
        (re.compile(r'(?<![<>!])<(?!=)'), "lt"),
    ]

    def _scan_operators(self, text):
        clean = re.sub(r'"[^"]*"', '""', text)
        clean = re.sub(r"'[01xXzZ_bBoOdDhH\d]+'", "''", clean)

        ops = set()
        if re.search(r"\bcase[xz]?\s*\(", clean):
            ops.add("case")

        for pattern, name in self._OP_PATTERNS:
            if pattern.search(clean):
                ops.add(name)
        return list(ops)

    def _extract_lhs_signals(self, text):
        sigs = []
        for m in re.finditer(r"\b(\w+)\s*(?:\[[^\]]*\])?\s*<=", text):
            sigs.append(m.group(1))
        for m in re.finditer(r"\b(\w+)\s*(?:\[[^\]]*\])?\s*=", text):
            sigs.append(m.group(1))
        return list(dict.fromkeys(sigs))

    def _extract_rhs_signals(self, text):
        keywords = {
            "begin", "end", "if", "else", "case", "endcase",
            "always", "assign", "wire", "reg", "logic", "posedge",
            "negedge", "default", "for", "while",
        }
        return [
            w for w in re.findall(r"\b([a-zA-Z_]\w*)\b", text)
            if w not in keywords and not w.isdigit()
        ][:20]


# ─────────────────────────────────────────────────────────────────────────────
# PATTERN MATCHER
# ─────────────────────────────────────────────────────────────────────────────

class PatternMatcher:

    def classify_module(self, module_info):
        name = module_info["name"].lower()
        all_ops = set()
        for ab in module_info["always_blocks"]:
            all_ops.update(ab["operators"])
        for as_ in module_info["assign_blocks"]:
            all_ops.update(as_["operators"])

        return self._score(name, all_ops,
                           any(ab["sensitivity"] for ab in module_info["always_blocks"]))

    def classify_always(self, block):
        name = " ".join(block.get("writes", []) + block.get("reads", []))
        ops = set(block["operators"])
        clocked = bool(re.search(r"posedge|negedge", block.get("sensitivity", "")))
        return self._score(name.lower(), ops, clocked)

    def classify_assign_group(self, assigns):
        ops = set()
        names = []
        for a in assigns:
            ops.update(a["operators"])
            names.append(a["lhs"])
        return self._score(" ".join(names).lower(), ops, False)

    def _score(self, name_str, ops, is_clocked):
        scores = {}
        ops = set(ops)

        for pat_key in PATTERN_PRIORITY:
            pat = PATTERN_LIBRARY[pat_key]
            s = 0.0

            # Name hints
            for hint in pat["name_hints"]:
                if len(hint) <= 3:
                    if re.search(r'(?<![a-zA-Z0-9_])' + re.escape(hint) + r'(?![a-zA-Z0-9_])', name_str):
                        s += 0.6
                else:
                    if hint in name_str:
                        s += 0.6

            # Operator rules
            if "multiply" in ops:
                if pat_key == "multiplier":
                    s += 0.9 if len(ops) <= 2 else 0.7
                elif pat_key == "alu":
                    s += 0.4
            if "divide" in ops:
                if pat_key in ("alu",):
                    s += 0.3
            if "add" in ops or "subtract" in ops:
                if pat_key == "adder":
                    s += 0.4
                if pat_key in ("alu", "counter"):
                    s += 0.25
                if pat_key == "multiplier":
                    s += 0.1
            if "case" in ops:
                if pat_key == "state_machine" and is_clocked:
                    s += 0.7
                if pat_key == "mux":
                    s += 0.35
            if "ternary" in ops:
                if pat_key == "mux":
                    s += 0.4
                if pat_key == "alu":
                    s += 0.1
            if "nbassign" in ops and is_clocked:
                if pat_key in ("register", "counter", "state_machine", "fifo", "memory"):
                    s += 0.3
            if any(op in ops for op in ("shift_left", "shift_right", "arith_shift_left", "arith_shift_right")):
                if pat_key == "shift":
                    s += 0.6
                if pat_key in ("alu", "counter"):
                    s += 0.1
            if any(op in ops for op in ("equal", "not_equal", "gt", "lt", "gte")):
                if pat_key == "comparator":
                    s += 0.45
                if pat_key in ("alu",):
                    s += 0.1
            if "and" in ops or "or" in ops or "xor" in ops:
                if pat_key == "combinational":
                    s += 0.2
                if pat_key == "alu":
                    s += 0.15
            if "add" in ops and "nbassign" in ops and is_clocked and pat_key == "fifo":
                s += 0.35
            if pat_key == "register" and "nbassign" in ops and is_clocked:
                significant = ops - {"nbassign"}
                if len(significant) == 0:
                    s += 0.2
            _alu_ops = ops & {"multiply","add","subtract","and","or","xor",
                               "shift_left","shift_right","arith_shift_left","arith_shift_right"}
            if pat_key == "alu" and len(_alu_ops) >= 2:
                s += 0.3

            # Clock sensitivity bonus
            if is_clocked and pat.get("sensitivity"):
                s += 0.15
            if not is_clocked and not pat.get("sensitivity") and pat_key != "state_machine":
                s += 0.05

            # Penalties
            if pat_key == "fifo" and "multiply" in ops:
                s -= 0.4
            if pat_key == "memory" and "multiply" in ops:
                s -= 0.3
            if pat_key == "state_machine" and "multiply" in ops:
                s -= 0.4

            scores[pat_key] = max(0.0, s)

        best = max(scores, key=lambda k: scores[k])
        conf = min(scores[best], 1.0)
        if conf < 0.1:
            return "combinational", 0.2
        return best, conf


# ─────────────────────────────────────────────────────────────────────────────
# GRAPH BUILDER
# ─────────────────────────────────────────────────────────────────────────────

class GraphBuilder:

    def __init__(self):
        self.matcher = PatternMatcher()
        self._block_counter = 0

    def build(self, modules, file_paths):
        module_map = {m["name"]: m for m in modules}

        # Classify each module
        classified = {}
        for m in modules:
            pat, conf = self.matcher.classify_module(m)
            classified[m["name"]] = (pat, conf)

        # Find which modules are instantiated by others
        instantiated_by = {}   # mod_name → list of parent module names
        for m in modules:
            for inst in m["instances"]:
                instantiated_by.setdefault(inst["module"], []).append(m["name"])

        # Top-level = not instantiated by anyone
        top_candidates = [m["name"] for m in modules if m["name"] not in instantiated_by]
        if not top_candidates:
            top_candidates = [modules[0]["name"]] if modules else ["unknown"]

        # If multiple top candidates, prefer the one whose reachable subtree
        # covers the most UNIQUE modules — that's the real "top".
        def _subtree_size(name):
            seen, queue = set(), [name]
            while queue:
                nm = queue.pop()
                if nm in seen or nm not in module_map: continue
                seen.add(nm)
                for inst in module_map[nm]["instances"]:
                    queue.append(inst["module"])
            return len(seen)

        top_name = max(top_candidates, key=_subtree_size)

        # Compute reachable set (BFS from top)
        reachable = set()
        queue = [top_name]
        while queue:
            nm = queue.pop()
            if nm in reachable:
                continue
            reachable.add(nm)
            if nm in module_map:
                for inst in module_map[nm]["instances"]:
                    queue.append(inst["module"])

        # Hierarchy depth from top
        depth = {top_name: 0}
        queue = [top_name]
        while queue:
            nm = queue.pop(0)
            if nm in module_map:
                for inst in module_map[nm]["instances"]:
                    child = inst["module"]
                    if child not in depth:
                        depth[child] = depth[nm] + 1
                        queue.append(child)

        # Orphans: modules parsed but not reachable from top
        orphans = [m["name"] for m in modules if m["name"] not in reachable]

        # Build graph for each module
        graph_modules = {}
        for m in modules:
            gm = self._build_module_graph(m, module_map, classified)
            gm["is_top"] = (m["name"] == top_name)
            gm["is_orphan"] = (m["name"] in orphans)
            gm["hierarchy_depth"] = depth.get(m["name"], -1)
            gm["instantiated_by"] = instantiated_by.get(m["name"], [])
            gm["file"] = m.get("file", "")
            gm["filepath"] = m.get("filepath", "")
            gm["line_count"] = m.get("line_count", 0)
            graph_modules[m["name"]] = gm

        return {
            "design_name": top_name,
            "files": [os.path.basename(p) for p in file_paths],
            "file_paths": [str(p) for p in file_paths],
            "top_module": top_name,
            "top_candidates": top_candidates,
            "module_names": [m["name"] for m in modules],
            "orphan_modules": orphans,
            "modules": graph_modules,
        }

    def _build_module_graph(self, module_info, module_map, classified):
        name = module_info["name"]
        ports = module_info["ports"]
        blocks = []

        # ── Sub-module instances ──────────────────────────────────────────
        for inst in module_info["instances"]:
            pat, conf = classified.get(inst["module"], ("unknown", 0.5))
            pat_info = PATTERN_LIBRARY.get(pat, PATTERN_LIBRARY["combinational"])
            bid = self._uid(inst["instance"])
            sub_mod = module_map.get(inst["module"])
            sub_ports = sub_mod["ports"] if sub_mod else []
            inputs  = [{"name": p["name"], "width": p["width"]}
                       for p in sub_ports if p["dir"] == "input"]
            outputs = [{"name": p["name"], "width": p["width"]}
                       for p in sub_ports if p["dir"] == "output"]
            # Map connected signals from port_connections
            port_conns = inst.get("port_connections", {})
            blocks.append({
                "id": bid,
                "label": inst["instance"],
                "sublabel": inst["module"],
                "type": pat,
                "color": pat_info["color"],
                "icon": pat_info["icon"],
                "confidence": round(conf, 2),
                "inputs": inputs[:6] or [{"name": "in", "width": "0"}],
                "outputs": outputs[:4] or [{"name": "out", "width": "0"}],
                "port_connections": port_conns,
                "drilldown_module": inst["module"] if inst["module"] in module_map else None,
                "drilldown_composition": pat_info.get("composition", []),
                "drilldown_gates": pat_info.get("gate_composition", []),
                "source": "instance",
                "instance_of": inst["module"],
            })

        # ── Always blocks ─────────────────────────────────────────────────
        for ab in module_info["always_blocks"]:
            pat, conf = self.matcher.classify_always(ab)
            pat_info = PATTERN_LIBRARY.get(pat, PATTERN_LIBRARY["combinational"])
            bid = self._uid(ab["id"])
            blocks.append({
                "id": bid,
                "label": pat_info["label"],
                "sublabel": f"always @({ab['sensitivity'] or '*'})",
                "type": pat,
                "color": pat_info["color"],
                "icon": pat_info["icon"],
                "confidence": round(conf, 2),
                "inputs": [{"name": s, "width": "0"} for s in (ab["reads"][:4] or ["in"])],
                "outputs": [{"name": s, "width": "0"} for s in (ab["writes"][:4] or ["out"])],
                "drilldown_module": None,
                "drilldown_composition": pat_info.get("composition", []),
                "drilldown_gates": pat_info.get("gate_composition", []),
                "source": "always",
                "sensitivity": ab["sensitivity"],
                "operators": ab["operators"],
                "snippet": ab["text_snippet"],
            })

        # ── Assign statements (group by output signal prefix) ─────────────
        assign_groups = self._group_assigns(module_info["assign_blocks"])
        for grp_label, assigns in assign_groups.items():
            pat, conf = self.matcher.classify_assign_group(assigns)
            pat_info = PATTERN_LIBRARY.get(pat, PATTERN_LIBRARY["combinational"])
            bid = self._uid(grp_label)
            output_names = [a["lhs"] for a in assigns]
            inputs_set = set()
            for a in assigns:
                inputs_set.update(re.findall(r"\b([a-zA-Z_]\w*)\b", a["rhs"]))
            inputs_set -= set(output_names)
            blocks.append({
                "id": bid,
                "label": pat_info["label"],
                "sublabel": f"assign ({', '.join(output_names[:2])}{'...' if len(output_names)>2 else ''})",
                "type": pat,
                "color": pat_info["color"],
                "icon": pat_info["icon"],
                "confidence": round(conf, 2),
                "inputs": [{"name": s, "width": "0"} for s in list(inputs_set)[:4]] or [{"name": "in", "width": "0"}],
                "outputs": [{"name": s, "width": "0"} for s in output_names[:4]],
                "drilldown_module": None,
                "drilldown_composition": pat_info.get("composition", []),
                "drilldown_gates": pat_info.get("gate_composition", []),
                "source": "assign",
                "operators": list(set().union(*[set(a["operators"]) for a in assigns])),
            })

        connections = self._infer_connections(blocks, ports)

        return {
            "id": name,
            "name": name,
            "ports": ports,
            "blocks": blocks,
            "connections": connections,
        }

    def _group_assigns(self, assigns):
        if not assigns:
            return {}
        groups = {}
        for a in assigns:
            key = a["lhs"][:6] if len(a["lhs"]) > 6 else a["lhs"]
            groups.setdefault(key, []).append(a)
        return groups

    def _infer_connections(self, blocks, ports):
        """
        Connect blocks whose output names match another block's input names.
        Also uses port_connections dicts from instantiations.
        """
        connections = []
        seen = set()

        # Build signal → block lookup from port_connections
        signal_to_src = {}   # signal_name → (block_id, port_name)
        for b in blocks:
            for op in b["outputs"]:
                pname = op["name"] if isinstance(op, dict) else op
                signal_to_src[pname] = (b["id"], pname)
            # For instances, map the connected signals to their output port names
            for port, sig in b.get("port_connections", {}).items():
                output_names = [o["name"] if isinstance(o, dict) else o for o in b["outputs"]]
                if port in output_names:
                    signal_to_src[sig] = (b["id"], port)

        for dst in blocks:
            dst_pc = dst.get("port_connections", {})
            for inp in dst["inputs"]:
                in_port = inp["name"] if isinstance(inp, dict) else inp
                if in_port in ("clk", "rst", "reset", "in", "out"):
                    continue
                # For instance blocks, resolve port → actual signal via port_connections
                in_signal = dst_pc.get(in_port, in_port)
                # Try the resolved signal name first, then the port name itself
                for lookup in ([in_signal] if in_signal != in_port else [in_port]):
                    if lookup in signal_to_src:
                        src_id, src_port = signal_to_src[lookup]
                        if src_id != dst["id"]:
                            key = (src_id, src_port, dst["id"], in_port)
                            if key not in seen:
                                seen.add(key)
                                connections.append({
                                    "id": f"conn_{len(connections)}",
                                    "from_block": src_id,
                                    "from_port": src_port,
                                    "to_block": dst["id"],
                                    "to_port": in_port,
                                    "label": lookup,
                                })
                        break

        # Fallback: name-matching heuristic
        for src in blocks:
            for dst in blocks:
                if src["id"] == dst["id"]:
                    continue
                src_outs = [o["name"] if isinstance(o, dict) else o for o in src["outputs"]]
                dst_ins  = [i["name"] if isinstance(i, dict) else i for i in dst["inputs"]]
                for out_port in src_outs:
                    if out_port in ("clk","rst","reset","in","out"):
                        continue
                    for in_port in dst_ins:
                        if out_port == in_port:
                            key = (src["id"], out_port, dst["id"], in_port)
                            if key not in seen:
                                seen.add(key)
                                connections.append({
                                    "id": f"conn_{len(connections)}",
                                    "from_block": src["id"],
                                    "from_port": out_port,
                                    "to_block": dst["id"],
                                    "to_port": in_port,
                                    "label": out_port,
                                })
        return connections

    def _uid(self, base):
        self._block_counter += 1
        safe = re.sub(r'\W+', '_', base)
        return f"blk_{self._block_counter}_{safe}"


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

class RTLEngine:
    def __init__(self):
        self.parser = VerilogParser()
        self.builder = GraphBuilder()

    # ── Loose instance pre-scanner ──────────────────────────────────────────
    # Pattern 1: simple  "mod_name  inst_name ("
    _LOOSE_SIMPLE_RE = re.compile(r'\b([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*\(')
    # Pattern 2: parameterised  "mod_name #("  — catches nested-paren param blocks
    _LOOSE_PARAM_RE  = re.compile(r'\b([A-Za-z_]\w*)\s*#\s*\(')
    _KW_SET = {
        'begin','end','if','else','case','casex','casez','endcase','always',
        'initial','assign','wire','reg','logic','input','output','inout',
        'parameter','localparam','module','endmodule','integer','genvar',
        'generate','endgenerate','for','while','repeat','forever','fork',
        'join','posedge','negedge','task','function','endtask','endfunction',
        'signed','unsigned','defparam',
    }

    def _loose_scan_instances(self, src_text):
        """
        Raw heuristic: find identifiers that look like module names in
        instantiation context — without needing to know module names first.
        Uses two patterns to handle both plain and parameterised instantiations.
        """
        clean = re.sub(r'/\*.*?\*/', ' ', src_text, flags=re.DOTALL)
        clean = re.sub(r'//[^\n]*', '', clean)
        candidates = set()
        # Pattern 1: plain  mod_name inst_name (
        for m in self._LOOSE_SIMPLE_RE.finditer(clean):
            name = m.group(1)
            if name not in self._KW_SET:
                candidates.add(name)
        # Pattern 2: parameterised  mod_name #(
        for m in self._LOOSE_PARAM_RE.finditer(clean):
            name = m.group(1)
            if name not in self._KW_SET:
                candidates.add(name)
        return candidates

    def analyze(self, file_paths, extra_search_dirs=None):
        """
        Parse files and auto-discover any referenced modules not yet found.
        Uses two strategies:
          1. Loose pre-scan for potential instance names before full parsing
          2. Iterative post-parse discovery for anything still missing
        """
        search_dirs = set(Path(fp).parent.resolve() for fp in file_paths)
        if extra_search_dirs:
            for d in extra_search_dirs:
                search_dirs.add(Path(d).resolve())

        parsed_paths = {str(Path(fp).resolve()) for fp in file_paths}

        print(f"  Parsing {len(parsed_paths)} file(s)...")

        # ── Phase 1: loose pre-scan to bootstrap discovery ──────────────────
        potential_names = set()
        for fp in list(parsed_paths):
            try:
                with open(fp, "r", errors="replace") as f:
                    src = f.read()
                potential_names.update(self._loose_scan_instances(src))
            except Exception:
                pass

        for name in potential_names:
            for d in list(search_dirs):
                for ext in [".v", ".sv"]:
                    candidate = d / f"{name}{ext}"
                    if candidate.exists():
                        rpath = str(candidate.resolve())
                        if rpath not in parsed_paths:
                            parsed_paths.add(rpath)
                            search_dirs.add(candidate.parent)
                            print(f"  Auto-discovered: {candidate.name}")
                        break

        # ── Phase 2: iterative post-parse discovery ─────────────────────────
        for _round in range(8):
            modules = self.parser.parse_files(list(parsed_paths))
            known_names = {m["name"] for m in modules}

            referenced = set()
            for m in modules:
                for inst in m["instances"]:
                    referenced.add(inst["module"])

            missing = referenced - known_names
            if not missing:
                break

            found_any = False
            for mod_name in missing:
                for d in list(search_dirs):
                    for ext in [".v", ".sv", ".vh"]:
                        candidate = d / f"{mod_name}{ext}"
                        if candidate.exists():
                            rpath = str(candidate.resolve())
                            if rpath not in parsed_paths:
                                parsed_paths.add(rpath)
                                search_dirs.add(candidate.parent)
                                print(f"  Auto-discovered: {candidate.name}")
                                found_any = True
                            break
            if not found_any:
                for mod_name in missing:
                    print(f"  Note: module '{mod_name}' not found in search paths")
                break

        # ── Final parse ──────────────────────────────────────────────────────
        modules = self.parser.parse_files(list(parsed_paths))
        if not modules:
            print("  Warning: no modules found.")
            return {"design_name": "empty", "files": [], "top_module": "",
                    "module_names": [], "orphan_modules": [], "modules": {}}

        print(f"  Found {len(modules)} module(s): {[m['name'] for m in modules]}")
        return self.builder.build(modules, list(parsed_paths))

    def analyze_directory(self, dir_path, recursive=True, exclude_tb=True):
        """
        Scan a directory for all .v/.sv files and analyze them.
        Excludes common testbench naming patterns by default.
        """
        dir_path = Path(dir_path).resolve()
        if recursive:
            candidates = list(dir_path.rglob("*.v")) + list(dir_path.rglob("*.sv"))
        else:
            candidates = list(dir_path.glob("*.v")) + list(dir_path.glob("*.sv"))

        if exclude_tb:
            tb_patterns = {"tb_", "_tb", "_test", "testbench", "_bench", "_sim", "_tb."}
            candidates = [
                f for f in candidates
                if not any(kw in f.stem.lower() for kw in tb_patterns)
            ]

        if not candidates:
            print(f"  Warning: no .v/.sv files found in {dir_path}")
            return {"design_name": "empty", "files": [], "top_module": "",
                    "module_names": [], "orphan_modules": [], "modules": {}}

        print(f"  Scanning {dir_path.name}/ → {len(candidates)} file(s)")
        return self.analyze([str(f) for f in candidates],
                            extra_search_dirs=[str(dir_path)])
