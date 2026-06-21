# RTLmap — Interactive RTL Block Diagram Viewer

> **[🌐 Project page](https://ikar_github.github.io/rtl_interactive_viewer/)** · Zero-dependency RTL visualiser for Verilog/SystemVerilog

Run it next to your Verilog/SystemVerilog code and instantly get a **hierarchical, clickable block diagram** in your browser — no EDA tools, no synthesis step, no external dependencies beyond Python 3.

```
python rtlmap.py design.v
```

---

## How it works

```
Your RTL ──► Parser ──► Pattern Matcher ──► Graph Builder ──► Browser Viewer
                             │
                      Pattern Library
                    (multiplier, ALU, FSM,
                     FIFO, register, …)
```

1. **Zero-dependency parser** reads your `.v` / `.sv` files directly — no Yosys, no Vivado, no compilation.
2. **Pattern library** identifies semantic blocks: sees `a * b` → draws a Multiplier; sees `always @(posedge clk)` with case statement → draws a State Machine.
3. **Hierarchical drill-down**: click any block to see its internals, even for behavioral RTL where the hierarchy isn't explicit in the source.

---

## Drill-down levels

```
Overview (all modules)
  └─ Module view        (sub-modules, always groups, assign groups)
       └─ Composition   (e.g., Multiplier → Partial Products → Adder Tree → CPA)
            └─ Gates    (XOR, AND, Full Adder, Half Adder, …)
```

Press **Esc** or click **← Back** to go up a level.

---

## Quick start

```bash
# Single file
python rtlmap.py my_design.v

# Multiple files (cross-file instantiations resolved automatically)
python rtlmap.py cpu.v alu.v regfile.v multiplier.v

# Custom port
python rtlmap.py *.v --port 8080

# Dump JSON and exit (useful for scripting / CI)
python rtlmap.py design.v --dump-json design.json

# Don't auto-open browser
python rtlmap.py design.v --no-browser
```

Browser opens at **http://localhost:7474** · Press **Ctrl+C** to stop.

---

## Detected block types

| Block | Trigger |
|---|---|
| **Multiplier** | `*` operator, name hints (mul, mult) |
| **Adder / Subtractor** | `+` / `-`, name hints (add, adder, sum) |
| **ALU** | Multiple arithmetic + logic operators together |
| **Register / FF** | `always @(posedge clk)` with simple `<=` |
| **Counter** | Clocked `<=` with `+1` increment |
| **Multiplexer** | Ternary `?:` or `case` statement |
| **State Machine** | Clocked `case` on a state register |
| **Comparator** | `==`, `!=`, `<`, `>` |
| **Shifter** | `<<`, `>>`, `<<<`, `>>>` |
| **Memory / RAM** | Array writes in `always @(posedge clk)` |
| **FIFO** | Dual pointer + memory array pattern |
| **Combinational** | Everything else |

Unknown logic is grouped by `always` or `assign` boundary — you always see something meaningful.

---

## Keyboard shortcuts

| Key | Action |
|---|---|
| **Scroll** | Zoom in/out |
| **Drag** | Pan |
| **Click** | Select block, open details panel |
| **Double-click** | Drill into block |
| **F** | Fit to screen |
| **Esc** | Go back one level |

---

## File layout

```
rtl_interactive_viewer/
├── rtlmap.py        # CLI entry point + HTTP server (stdlib only)
├── rtl_engine.py     # Parser, pattern library, graph builder
├── static/
│   └── index.html    # Self-contained interactive frontend
└── examples/
    ├── multiplier.v  # 8×8 multiplier with full/half adder cells
    ├── alu.v         # 32-bit ALU + register file
    └── processor.v   # RISC-style processor (top-level demo)
```

No `pip install` needed. Pure Python 3.8+.

---

## Try the examples

```bash
# Full processor design (shows all block types)
python rtlmap.py examples/processor.v examples/alu.v examples/multiplier.v

# Just the multiplier (drill down to see Full Adder → gates)
python rtlmap.py examples/multiplier.v
```

---

## How this differs from other tools

| Feature | RTLmap | Yosys `show` | Vivado RTL viewer | netlistsvg |
|---|---|---|---|---|
| No EDA install needed | ✅ | ❌ | ❌ | partial |
| Works on behavioral RTL | ✅ | ❌ | ✅ | ❌ |
| Semantic block detection | ✅ | ❌ | limited | ❌ |
| Interactive drill-down | ✅ | ❌ | limited | ❌ |
| Browser-based | ✅ | ❌ | ❌ | ✅ |
| Zero dependencies | ✅ | ❌ | ❌ | ❌ |
| Gate-level view | conceptual | ✅ | ✅ | ✅ |

The key insight: **you don't need to synthesize to understand your design**. RTLmap works directly on your source files, identifying *intent* (this is a multiplier) rather than just structure (these are 2,048 NAND gates).

---

## Roadmap

- [ ] GitHub URL input → instant block diagram from any public repo  
- [ ] SystemVerilog interface and `always_ff` / `always_comb` support
- [ ] User-defined pattern library (add your own block definitions)
- [ ] Signal trace highlighting (click a wire, see where it goes)
- [ ] Export to SVG / PNG
- [ ] Dark/light theme toggle
