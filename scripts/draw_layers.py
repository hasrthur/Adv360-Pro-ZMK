#!/usr/bin/env python3
"""Render every layer of the ported layout as an HTML page.

Usage: python3 scripts/draw_layers.py glove80/layout.json > glove80/layers.html
"""
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glove80_to_adv360 as g  # noqa: E402

KEYS = {
    **{f"N{i}": str(i) for i in range(10)},
    **{f"KP_N{i}": f"KP{i}" for i in range(10)},
    "EQUAL": "=", "MINUS": "-", "SEMI": ";", "SQT": "'", "SINGLE_QUOTE": "'", "BSLH": "\\",
    "FSLH": "/", "COMMA": ",", "DOT": ".", "GRAVE": "`", "LBKT": "[", "RBKT": "]",
    "RET": "⏎", "SPACE": "␣", "BSPC": "⌫", "DEL": "⌦", "TAB": "⇥", "ESC": "Esc",
    "LEFT": "←", "RIGHT": "→", "UP": "↑", "DOWN": "↓",
    "LEFT_ARROW": "←", "RIGHT_ARROW": "→", "UP_ARROW": "↑", "DOWN_ARROW": "↓",
    "HOME": "Home", "END": "End", "PG_UP": "PgUp", "PG_DN": "PgDn", "INS": "Ins",
    "CAPS": "Caps", "PSCRN": "PrtSc", "PRINTSCREEN": "PrtSc", "SCROLLLOCK": "ScrLk",
    "PAUSE_BREAK": "Pause", "K_APP": "Menu", "KP_NUM": "NumLk", "KP_SLASH": "KP/",
    "KP_MULTIPLY": "KP*", "KP_MINUS": "KP-", "KP_PLUS": "KP+", "KP_DOT": "KP.",
    "KP_ENTER": "KP⏎",
    "LSHFT": "⇧", "RSHFT": "⇧", "LCTRL": "⌃", "RCTRL": "⌃", "LALT": "⌥", "RALT": "⌥",
    "LGUI": "⌘", "RGUI": "⌘",
    "C_PREV": "⏮", "C_NEXT": "⏭", "C_PP": "⏯", "C_MUTE": "🔇", "C_VOL_UP": "🔊",
    "C_VOL_DN": "🔉", "C_BRI_UP": "🔆", "C_BRI_DN": "🔅",
}
MODS = {"LG": "⌘", "LS": "⇧", "LA": "⌥", "LC": "⌃", "RG": "⌘", "RS": "⇧", "RA": "⌥", "RC": "⌃"}
MOUSE = {
    "MOVE_UP": "🖱↑", "MOVE_DOWN": "🖱↓", "MOVE_LEFT": "🖱←", "MOVE_RIGHT": "🖱→",
    "SCRL_UP": "⇞ scroll", "SCRL_DOWN": "⇟ scroll", "SCRL_LEFT": "scroll ←", "SCRL_RIGHT": "scroll →",
    "LCLK": "L click", "RCLK": "R click", "MCLK": "M click", "MB4": "Back", "MB5": "Fwd",
}
MACROS = {
    "&cur_SELECT_LINE_macos_v1_TKZ": "Sel line", "&cur_SELECT_WORD_macos_v1_TKZ": "Sel word",
    "&cur_SELECT_NONE_v1_TKZ": "Sel none", "&cur_EXTEND_LINE_macos_v1_TKZ": "Ext line",
    "&cur_EXTEND_WORD_macos_v1_TKZ": "Ext word", "&symb_dotdot_v1_TKZ": "..",
    "&lower": "Lower", "&bootloader": "BOOT", "&sys_reset": "Reset",
    "&rgui_copy": "Copy", "&rgui_cut": "Cut", "&rgui_paste": "Paste",
}


def key(code):
    m = re.fullmatch(r"(\w\w)\((.*)\)", code)
    if m and m.group(1) in MODS:
        return MODS[m.group(1)] + key(m.group(2))
    return KEYS.get(code, code)


def label(b, names):
    """Return (main label, hold label, css class)."""
    parts = b.split()
    v, args = parts[0], parts[1:]
    if v == "&trans":
        return "▽", "", "trans"
    if v == "&none":
        return "", "", "none"
    if v == "&kp":
        return key(args[0]), "", ""
    if re.match(r"&HRM_\w+_tap_v1B_TKZ", v):
        return key(args[0]), "", "roll"
    if v.startswith("&HRM_"):
        return key(args[1]), key(args[0]), "hrm"
    if v == "&CAPSWord_v1_TKZ":
        return "CapsWord", key(args[0]), "hrm"
    if v in ("&thumb_v2_TKZ", "&space_v3_TKZ"):
        return key(args[1]), names[int(args[0])], "lt"
    if v in ("&mo", "&to", "&tog"):
        verb = {"&mo": "hold", "&to": "→", "&tog": "toggle"}[v]
        return names[int(args[0])], verb, "layer"
    if v == "&sk":
        return key(args[0]), "sticky", "hrm"
    if v == "&mod_tab_v2_TKZ":
        return key(args[0]) + "⇥", "", ""
    if v in ("&mmv", "&msc", "&mkp"):
        return MOUSE.get(args[0], args[0]), "", "mouse"
    if v.startswith("&bt_"):
        return "BT " + v[-1], "", "sys"
    if v == "&bt":
        return {"BT_CLR": "BT clear", "BT_CLR_ALL": "BT clr ALL"}.get(args[0], " ".join(args)), "", "sys"
    if v == "&out":
        return "USB", "", "sys"
    if v == "&rgb_ug":
        return "RGB " + args[0][4:].lower(), "", "sys"
    if v == "&stp":
        return "🔋 Battery", "", "sys"
    if v in MACROS:
        return MACROS[v], "", "sys" if v in ("&bootloader", "&sys_reset") else ""
    return v.lstrip("&"), " ".join(args), ""


# (position, column, row, width, height) on a 16-wide grid per half. Rows 0-4 are the
# main block; rows 6-8 the thumb cluster.
def left_cells():
    cells = []
    for r, (start, n) in enumerate([(0, 7), (14, 7), (28, 7), (46, 6), (60, 5)]):
        cells += [(start + i, i + 1, r + 1, 1, 1) for i in range(n)]
    cells += [(35, 6, 6, 1, 1), (36, 7, 6, 1, 1), (52, 7, 7, 1, 1),
              (65, 5, 7, 1, 2), (66, 6, 7, 1, 2), (67, 7, 8, 1, 1)]
    return cells


def right_cells():
    cells = []
    for r, (start, n, off) in enumerate([(7, 7, 0), (21, 7, 0), (39, 7, 0), (54, 6, 1), (71, 5, 2)]):
        cells += [(start + i, i + 1 + off, r + 1, 1, 1) for i in range(n)]
    cells += [(37, 1, 6, 1, 1), (38, 2, 6, 1, 1), (53, 1, 7, 1, 1),
              (68, 1, 8, 1, 1), (69, 2, 7, 1, 2), (70, 3, 7, 1, 2)]
    return cells


def half(cells, adv, names):
    out = ['<div class="half">']
    for pos, c, r, w, h in cells:
        main, hold, cls = label(adv[pos], names)
        out.append(
            f'<div class="k {cls}" style="grid-column:{c}/span {w};grid-row:{r}/span {h}" '
            f'title="{pos}: {html.escape(adv[pos])}">'
            f'<span>{html.escape(main)}</span><small>{html.escape(hold)}</small></div>'
        )
    out.append("</div>")
    return "".join(out)


CSS = """
body{font:14px system-ui,sans-serif;background:#1e1e2e;color:#cdd6f4;margin:24px}
h2{margin:32px 0 8px}nav a{color:#89b4fa;margin-right:10px}
.board{display:flex;gap:56px}
.half{display:grid;grid-template-columns:repeat(7,58px);grid-auto-rows:50px;gap:4px}
.k{background:#313244;border-radius:6px;display:flex;flex-direction:column;align-items:center;
   justify-content:center;text-align:center;line-height:1.1;overflow:hidden}
.k span{font-size:13px}.k small{font-size:10px;color:#f9e2af}
.trans{background:#262637;color:#585b70}.none{background:#24243a}
.hrm{background:#45475a}.lt{background:#1e3a5f}.layer{background:#3b2f5c}
.roll{background:#2d3b35}.mouse{background:#2f3d4f}.sys{background:#5c2f3b}
.legend span{display:inline-block;padding:2px 8px;border-radius:4px;margin-right:6px}
"""


def main():
    d = json.load(open(sys.argv[1]))
    g.HOLD_TAPS.update(h["name"] for h in d["holdTaps"])
    names = d["layer_names"]
    parts = [f"<!doctype html><meta charset=utf-8><title>Adv360 layers</title><style>{CSS}</style>",
             f"<h1>{html.escape(d['title'])} → Advantage360</h1>",
             '<p class="legend"><span class="hrm">tap / <small>hold</small></span>'
             '<span class="lt">tap / <small>hold layer</small></span><span class="layer">layer</span>'
             '<span class="roll">same-hand roll (types plain)</span><span class="trans">▽ transparent</span>'
             '<span class="sys">system</span> Hover a key for its raw binding.</p><nav>']
    parts += [f'<a href="#l{i}">{i} {html.escape(n)}</a>' for i, n in enumerate(names)]
    parts.append("</nav>")
    for i, (name, gl) in enumerate(zip(names, d["layers"])):
        adv = g.layer_bindings(name, gl)
        parts.append(f'<h2 id="l{i}">{i} · {html.escape(name)}</h2><div class="board">')
        parts.append(half(left_cells(), adv, names) + half(right_cells(), adv, names) + "</div>")
    print("\n".join(parts))


if __name__ == "__main__":
    main()
