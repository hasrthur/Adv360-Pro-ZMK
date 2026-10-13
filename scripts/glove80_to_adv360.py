#!/usr/bin/env python3
"""Generate config/adv360.keymap from a Glove80 Layout Editor JSON export.

Writes config/adv360.keymap, plus layers.html (a drawing of every layer) next to the export.

Usage: python3 scripts/glove80_to_adv360.py glove80/layout.json
"""
import json
import os
import re
import sys

ADV_KEYS = 76

# Glove80 position -> Adv360 position. Glove80 positions not listed (the F-row) are dropped.
POS = {}
for g, a in zip(range(10, 16), range(0, 6)): POS[g] = a        # number row L
for g, a in zip(range(16, 22), range(8, 14)): POS[g] = a        # number row R
for g, a in zip(range(22, 28), range(14, 20)): POS[g] = a       # top row L
for g, a in zip(range(28, 34), range(22, 28)): POS[g] = a       # top row R
for g, a in zip(range(34, 40), range(28, 34)): POS[g] = a       # home row L
for g, a in zip(range(40, 46), range(40, 46)): POS[g] = a       # home row R
for g, a in zip(range(46, 52), range(46, 52)): POS[g] = a       # bottom alpha L
for g, a in zip(range(58, 64), range(54, 60)): POS[g] = a       # bottom alpha R
for g, a in zip(range(64, 69), range(60, 65)): POS[g] = a       # bottom row L
for g, a in zip(range(75, 80), range(71, 76)): POS[g] = a       # bottom row R
POS.update({  # thumbs
    52: 35, 53: 36, 54: 52,   # upper arc L -> top pair + small key
    55: 53, 56: 37, 57: 38,   # upper arc R -> small key + top pair
    69: 65, 70: 66, 71: 67,   # lower arc L -> big, big, small
    72: 68, 73: 69, 74: 70,   # lower arc R -> small, big, big
})

INNER_L = [6, 20, 34]
INNER_R = [7, 21, 39]
THUMBS = [35, 36, 52, 65, 66, 67, 37, 38, 53, 68, 69, 70]
LEFT = list(range(0, 7)) + list(range(14, 21)) + list(range(28, 35)) + list(range(46, 52)) + list(range(60, 65))
RIGHT = list(range(7, 14)) + list(range(21, 28)) + list(range(39, 46)) + list(range(54, 60)) + list(range(71, 76))

# Glove80 F-row bindings relocated onto the inner column, per layer name.
INNER = {
    "HRM_macOS": {6: "&kp C_PREV", 20: "&kp C_PP", 34: "&kp C_NEXT",
                  7: "&kp C_VOL_UP", 21: "&kp C_VOL_DN", 39: "&kp C_MUTE"},
    "Lower": {6: "&kp C_BRI_UP", 20: "&kp C_BRI_DN", 34: "&kp PAUSE_BREAK"},
    "Magic": {7: "&bt BT_CLR", 21: "&bt BT_CLR_ALL", 39: "&stp STP_BAT"},
}

# MoErgo built-ins that don't exist on the Adv360.
REPLACE = {
    "&magic": "&mo 19",
    "&reset": "&sys_reset",
}
DROP_MACROS = {"&mstr1_v1_TKZ", "&mstr2_v1_TKZ"}
HOLD_TAPS = set()  # filled from the export in main()


def fmt_param(p):
    if isinstance(p, (int, str)):
        return "0" if p == "MACRO_PLACEHOLDER" else str(p)
    v = p["value"]
    if v == "MACRO_PLACEHOLDER":
        v = 0
    if p.get("params"):
        return f"{v}({','.join(fmt_param(x) for x in p['params'])})"
    return str(v)


def fmt(b):
    v = b["value"]
    if v in DROP_MACROS:
        return "&none"
    if v in REPLACE:
        return REPLACE[v]
    params = [fmt_param(p) for p in b.get("params", [])]
    if v in HOLD_TAPS:  # hold-taps always take two cells; the editor omits unused ones
        params += ["0"] * (2 - len(params))
    return " ".join([v] + params)


def ident(name):
    return re.sub(r"[^A-Za-z0-9_]", "_", name.lstrip("&"))


def map_positions(gpositions, name):
    out = set()
    for g in gpositions:
        if g in POS:
            out.add(POS[g])
        elif not 0 <= g <= 9:
            sys.exit(f"{name}: unmapped Glove80 position {g}")
    return out


def hold_trigger_positions(ht):
    """Translate positions, then add the inner column of whichever hand the list covers."""
    mapped = map_positions(ht["holdTriggerKeyPositions"], ht["name"])
    if mapped >= set(RIGHT) - set(INNER_R):
        mapped |= set(INNER_R)
    if mapped >= set(LEFT) - set(INNER_L):
        mapped |= set(INNER_L)
    return sorted(mapped)


def hold_tap(ht):
    lines = [
        f"        {ident(ht['name'])}: {ident(ht['name'])} {{",
        '            compatible = "zmk,behavior-hold-tap";',
        "            #binding-cells = <2>;",
        f"            bindings = <{ht['bindings'][0]}>, <{ht['bindings'][1]}>;",
        f"            tapping-term-ms = <{ht['tappingTermMs']}>;",
    ]
    if "flavor" in ht:
        lines.append(f'            flavor = "{ht["flavor"]}";')
    if "quickTapMs" in ht:
        lines.append(f"            quick-tap-ms = <{ht['quickTapMs']}>;")
    if "requirePriorIdleMs" in ht:
        lines.append(f"            require-prior-idle-ms = <{ht['requirePriorIdleMs']}>;")
    if ht.get("holdTriggerOnRelease"):
        lines.append("            hold-trigger-on-release;")
    if "holdTriggerKeyPositions" in ht:
        pos = " ".join(str(p) for p in hold_trigger_positions(ht))
        lines.append(f"            hold-trigger-key-positions = <{pos}>;")
    lines.append("        };")
    return "\n".join(lines)


def macro(m):
    n = len(m.get("params", []))
    compatible = ["zmk,behavior-macro", "zmk,behavior-macro-one-param", "zmk,behavior-macro-two-param"][n]
    lines = [
        f"        {ident(m['name'])}: {ident(m['name'])} {{",
        f'            compatible = "{compatible}";',
        f"            #binding-cells = <{n}>;",
    ]
    if "waitMs" in m:
        lines.append(f"            wait-ms = <{m['waitMs']}>;")
    if "tapMs" in m:
        lines.append(f"            tap-ms = <{m['tapMs']}>;")
    bindings = ", ".join(f"<{fmt(b)}>" for b in m["bindings"])
    lines.append(f"            bindings = {bindings};")
    lines.append("        };")
    return "\n".join(lines)


def combo(c):
    keys = map_positions(c["keyPositions"], c["name"])
    if len(keys) != len(c["keyPositions"]):
        return None  # uses an F-row key
    lines = [
        f"        combo_{ident(c['name'])} {{",
        f"            bindings = <{fmt(c['binding'])}>;",
        f"            key-positions = <{' '.join(str(k) for k in sorted(keys))}>;",
        f"            timeout-ms = <{c.get('timeoutMs', 50)}>;",
    ]
    layers = c.get("layers", [-1])
    if layers != [-1]:
        lines.append(f"            layers = <{' '.join(str(l) for l in layers)}>;")
    lines.append("        };")
    return "\n".join(lines)


# Physical rows of the Adv360 keymap, in binding order.
ROWS = [
    list(range(0, 14)),
    list(range(14, 28)),
    list(range(28, 46)),
    list(range(46, 60)),
    list(range(60, 76)),
]


def layer(name, gl):
    adv = layer_bindings(name, gl)
    rows = "\n".join("            " + "  ".join(adv[a] for a in row) for row in ROWS)
    return (
        f"        layer_{ident(name)} {{\n"
        f'            display-name = "{name}";\n'
        f"            bindings = <\n{rows}\n            >;\n"
        f"        }};"
    )


def layer_bindings(name, gl):
    """Adv360 position -> binding string for one Glove80 layer."""
    adv = {}
    for g, a in POS.items():
        adv[a] = fmt(gl[g])
    is_trans_layer = all(b["value"] == "&trans" for b in gl)
    for a in INNER_L + INNER_R:
        adv[a] = INNER.get(name, {}).get(a, "&trans" if is_trans_layer else "&none")
    # Finger layers and Typing: let the inner column fall through to the base layer.
    if name in {"Typing"} or re.match(r"(Left|Right)(Index|Middy|Ringy|Pinky)$", name):
        for a in INNER_L + INNER_R:
            adv[a] = "&trans"
    assert len(adv) == ADV_KEYS, name
    return adv


def input_listener(il):
    out = [f"{il['code']} {{"]
    for node in il["nodes"]:
        procs = ", ".join(f"<{p['code']} {' '.join(str(x) for x in p['params'])}>" for p in node["inputProcessors"])
        out += [
            f"    {ident(node['code']).lower()} {{",
            f"        layers = <{' '.join(str(l) for l in node['layers'])}>;",
            f"        input-processors = {procs};",
            "    };",
        ]
    out.append("};")
    return "\n".join(out)


def main():
    d = json.load(open(sys.argv[1]))
    HOLD_TAPS.update(h["name"] for h in d["holdTaps"])
    if d.get("custom_defined_behaviors") or d.get("custom_devicetree"):
        sys.exit("custom devicetree in export is not handled")

    bt_macros = "\n".join(
        f"""        bt_{i}: bt_{i} {{
            compatible = "zmk,behavior-macro";
            #binding-cells = <0>;
            bindings = <&out OUT_BLE>, <&bt BT_SEL {i}>;
        }};"""
        for i in range(4)
    )
    lower = """        lower: lower {
            compatible = "zmk,behavior-tap-dance";
            #binding-cells = <0>;
            tapping-term-ms = <200>;
            bindings = <&mo 6>, <&to 6>;
        };"""

    macros = [m for m in d["macros"] if m["name"] not in DROP_MACROS]
    combos = [c for c in (combo(c) for c in d["combos"]) if c]

    keymap = f"""/*
 * GENERATED by scripts/glove80_to_adv360.py from "{d['title']}".
 * Do not edit by hand: change the Glove80 layout or the script and regenerate.
 */

#include <behaviors.dtsi>
#include <input/processors.dtsi>
#include <dt-bindings/zmk/keys.h>
#include <dt-bindings/zmk/bt.h>
#include <dt-bindings/zmk/outputs.h>
#include <dt-bindings/zmk/rgb.h>
#include <dt-bindings/zmk/backlight.h>
#include <dt-bindings/zmk/pointing.h>
#include <dt-bindings/zmk/stp.h>

/ {{
    /* MoErgo-only; Kinesis's ZMK has the x/y scalers but no scroll scaler. */
    /omit-if-no-ref/ zip_scroll_scaler: zip_scroll_scaler {{
        compatible = "zmk,input-processor-scaler";
        #input-processor-cells = <2>;
        type = <INPUT_EV_REL>;
        codes = <INPUT_REL_WHEEL INPUT_REL_HWHEEL>;
        track-remainders;
    }};
}};

{chr(10).join(input_listener(il) for il in d.get('inputListeners', []))}

/ {{
    behaviors {{
{lower}
{bt_macros}
{chr(10).join(hold_tap(h) for h in d['holdTaps'])}
    }};

    macros {{
{chr(10).join(macro(m) for m in macros)}
    }};

    combos {{
        compatible = "zmk,combos";
{chr(10).join(combos)}
    }};

    keymap {{
        compatible = "zmk,keymap";
{chr(10).join(layer(n, l) for n, l in zip(d['layer_names'], d['layers']))}
    }};
}};
"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "config", "adv360.keymap"), "w") as out:
        out.write(keymap)

    import draw_layers  # imports this module, so only at call time
    with open(os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "layers.html"), "w") as out:
        out.write(draw_layers.render(d))


if __name__ == "__main__":
    main()
