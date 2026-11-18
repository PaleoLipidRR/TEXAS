#!/usr/bin/env python
"""Skeletal drawings of isoprenoid GDGTs, generated from a short description.

Each glycerol dibiphytanyl glycerol tetraether (GDGT) is drawn the way organic
geochemists usually sketch it: two C40 biphytanyl chains as zigzag lines, methyl
branches as short stubs, cyclopentane rings as pentagons, and a glycerol at each
end. The drawing is computed from the carbon numbering, so the same code gives a
standalone SVG file or a drawing inside a matplotlib figure.

Chemistry encoded here
----------------------
* Biphytane backbone: 32 carbons with methyl branches at backbone carbons
  3, 7, 11, 15, 18, 22, 26 and 30 (3,7,11,15,18,22,26,30-octamethyldotriacontane),
  i.e. C-3, C-7, C-11, C-15 of each phytanyl half.
* A cyclopentane ring "at C-7" joins the methyl carbon on C-7 to C-10, so the
  ring holds C-7, C-8, C-9, C-10 and that methyl carbon. "7'" is the same ring
  in the other half of the chain. Rings "3" and "3'" (methyl on C-3 joined to
  C-6) are supported for GDGTs with more than four rings.
* Each chain end is ether-bound to a glycerol; the third glycerol carbon keeps
  its hydroxyl. ``glycerol="parallel"`` puts both free CH2OH groups on the same
  chain side, ``"antiparallel"`` on opposite sides.

What is NOT encoded: stereochemistry, and which end of a chain a ring sits at
relative to the glycerols (regiochemistry). The ring placements in ``GDGTS`` are
a drawing convention; edit them if you need a specific isomer. Crenarchaeol is
not included because its cyclohexane ring needs its own geometry.

Use
---
    python scripts/gdgt_structures.py --outdir figures/gdgt_structures

    from gdgt_structures import to_svg, draw
    to_svg("GDGT-2", "GDGT-2.svg", ring_fill="#FAC775")
    draw(ax, "GDGT-2")            # ax should have equal aspect
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

# name -> (rings on chain A, rings on chain B). Ring names: "7", "7'", "3", "3'".
GDGTS = {
    "GDGT-0": ((), ()),
    "GDGT-1": (("7",), ()),
    "GDGT-2": (("7",), ("7'",)),
    "GDGT-3": (("7", "7'"), ("7",)),
    "GDGT-4": (("7", "7'"), ("7", "7'")),
}

N_BACKBONE = 32
METHYLS = (3, 7, 11, 15, 18, 22, 26, 30)
# ring name -> (first backbone carbon of the ring, backbone carbon whose methyl closes it)
RING_SITES = {"7": (7, 7), "7'": (23, 26), "3": (3, 3), "3'": (27, 30)}

BOND = 1.0                                   # every length below is in bond lengths
DX = BOND * math.cos(math.radians(30))       # horizontal advance per zigzag bond
HALF = BOND * math.sin(math.radians(30)) / 2  # zigzag carbons sit at +/- HALF
PHI = (1 + math.sqrt(5)) / 2                 # pentagon diagonal / side
RING_DX = math.sqrt(PHI ** 2 - (2 * HALF) ** 2)   # horizontal span of a ring
CHAIN_SEP = 3.4                              # distance between the two chain axes
METHYL_LEN = 0.75
LABEL_GAP = 0.33                             # bond is cut this far from an atom label


def _chain(rings, total_dx):
    """Backbone of one biphytanyl chain, drawn left to right around y = 0.

    Returns (open polylines, ring polygons, methyl stubs, first carbon, last carbon).
    Odd-numbered carbons sit on the lower side of the zigzag.
    """
    sites = {RING_SITES[r][0]: RING_SITES[r][1] for r in rings}
    n_zig = (N_BACKBONE - 1) - 3 * len(sites)
    dx = (total_dx - len(sites) * RING_DX) / n_zig     # spread the slack evenly

    pos, polygons, used_methyls = {}, [], set()
    lines, current = [], []
    x, i = 0.0, 1
    while i <= N_BACKBONE:
        level = -1 if i % 2 else 1
        pos[i] = (x, level * HALF)
        current.append(pos[i])
        if i in sites:
            # Pentagon through C(i) .. C(i+3) plus the methyl carbon; C(i+3) lands on
            # the opposite zigzag level, exactly where it would be without the ring.
            v0 = pos[i]
            v3 = (x + RING_DX, -level * HALF)
            ux, uy = (v3[0] - v0[0]) / PHI, (v3[1] - v0[1]) / PHI
            nx, ny = -uy, ux                           # left-hand normal (upward here)
            def local(a, b):
                return (v0[0] + a * ux + b * nx, v0[1] + a * uy + b * ny)
            apex = local(PHI / 2, math.sin(math.radians(36)))
            v1 = local((PHI - 1) / 2, -math.sin(math.radians(72)))
            v2 = local((PHI + 1) / 2, -math.sin(math.radians(72)))
            polygons.append([v0, v1, v2, v3, apex])
            used_methyls.add(sites[i])
            lines.append(current)
            current = []
            x += RING_DX
            i += 3
            continue
        x += dx
        i += 1
    lines.append(current)

    stubs = []
    for m in METHYLS:
        if m in used_methyls:
            continue
        px, py = pos[m]
        stubs.append([(px, py), (px, py + math.copysign(METHYL_LEN, py))])
    return lines, polygons, stubs, pos[1], pos[N_BACKBONE]


def _shorten(p, q, gap):
    """Move point q toward p by ``gap`` (so a bond stops short of an atom label)."""
    d = math.hypot(q[0] - p[0], q[1] - p[1])
    t = max(d - gap, 0) / d
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def geometry(name_or_rings, glycerol="parallel"):
    """Line work of one GDGT in bond-length units (y up).

    Returns a dict with ``lines`` (open polylines), ``rings`` (closed pentagons),
    ``labels`` (x, y, text) and ``bbox`` (xmin, ymin, xmax, ymax).
    """
    rings_a, rings_b = GDGTS[name_or_rings] if isinstance(name_or_rings, str) else name_or_rings
    if glycerol not in ("parallel", "antiparallel"):
        raise ValueError("glycerol must be 'parallel' or 'antiparallel'")
    total_dx = (N_BACKBONE - 1) * DX
    y_a, y_b = CHAIN_SEP / 2, -CHAIN_SEP / 2

    lines, rings, labels, ends = [], [], [], {}
    for key, ring_names, y0, flip in (("a", rings_a, y_a, 1), ("b", rings_b, y_b, -1)):
        chain_lines, polygons, stubs, first, last = _chain(ring_names, total_dx)
        place = lambda p: (p[0], y0 + flip * p[1])     # chain B is mirrored top to bottom
        lines += [[place(p) for p in line] for line in chain_lines + stubs]
        rings += [[place(p) for p in poly] for poly in polygons]
        ends[key] = (place(first), place(last))

    # Glycerols. Chain A ends on the sn-3 carbon, chain B on the sn-2 carbon, which
    # also carries the free CH2OH (sn-1). Antiparallel swaps the roles at the right end.
    for side, direction in (("left", -1), ("right", 1)):
        idx = 0 if side == "left" else 1
        carbons = {}
        for key in ("a", "b"):
            c_end = ends[key][idx]
            inward = -math.copysign(1, c_end[1])
            oxygen = (c_end[0] + direction * DX, c_end[1] + inward * 0.5)
            g_y = math.copysign(0.5, c_end[1])
            rise = abs(oxygen[1] - g_y)
            g_x = oxygen[0] + direction * math.sqrt(max(1 - rise ** 2, 0.09))
            carbons[key] = (g_x, g_y)
            labels.append((oxygen[0], oxygen[1], "O"))
            lines.append([c_end, _shorten(c_end, oxygen, LABEL_GAP)])
            lines.append([_shorten(carbons[key], oxygen, LABEL_GAP), carbons[key]])
        lines.append([carbons["a"], carbons["b"]])
        sn2 = "a" if (glycerol == "antiparallel" and side == "right") else "b"
        gx, gy = carbons[sn2]
        out = math.copysign(1, gy)
        sn1 = (gx + direction * DX, gy + out * 0.5)
        hydroxyl = (sn1[0] + direction * DX, sn1[1] - out * 0.5)
        lines.append([carbons[sn2], sn1, _shorten(sn1, hydroxyl, LABEL_GAP + 0.12)])
        labels.append((hydroxyl[0] + direction * 0.22, hydroxyl[1], "HO" if direction < 0 else "OH"))

    xs = [p[0] for line in lines + rings for p in line] + [l[0] for l in labels]
    ys = [p[1] for line in lines + rings for p in line] + [l[1] for l in labels]
    pad = 0.8
    return {"lines": lines, "rings": rings, "labels": labels,
            "bbox": (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)}


def to_svg(name_or_rings, path=None, *, glycerol="parallel", scale=16.0, color="#222222",
           stroke_width=1.5, ring_fill="none", font_family="Helvetica, Arial, sans-serif",
           font_size=None, background="none"):
    """Return the molecule as an SVG string, and write it to ``path`` if given.

    scale        : pixels per bond length.
    stroke_width : line width in pixels.
    ring_fill    : fill color of the cyclopentane rings ("none" for outline only).
    font_size    : atom-label size in pixels (default 0.72 x scale).
    """
    geo = geometry(name_or_rings, glycerol)
    x0, y0, x1, y1 = geo["bbox"]
    width, height = (x1 - x0) * scale, (y1 - y0) * scale
    font_size = font_size or 0.72 * scale

    def pt(p):
        return f"{(p[0] - x0) * scale:.2f},{(y1 - p[1]) * scale:.2f}"

    title = name_or_rings if isinstance(name_or_rings, str) else "GDGT"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}" height="{height:.1f}" '
           f'viewBox="0 0 {width:.1f} {height:.1f}" role="img">',
           f"<title>{title}</title>"]
    if background != "none":
        out.append(f'<rect width="100%" height="100%" fill="{background}"/>')
    out.append(f'<g fill="none" stroke="{color}" stroke-width="{stroke_width}" '
               f'stroke-linecap="round" stroke-linejoin="round">')
    for ring in geo["rings"]:
        out.append(f'<polygon class="ring" fill="{ring_fill}" points="{" ".join(pt(p) for p in ring)}"/>')
    for line in geo["lines"]:
        out.append(f'<polyline points="{" ".join(pt(p) for p in line)}"/>')
    out.append("</g>")
    out.append(f'<g fill="{color}" font-family="{font_family}" font-size="{font_size:.1f}" '
               f'text-anchor="middle" dominant-baseline="central">')
    for x, y, text in geo["labels"]:
        out.append(f'<text x="{(x - x0) * scale:.2f}" y="{(y1 - y) * scale:.2f}">{text}</text>')
    out.append("</g></svg>")
    svg = "\n".join(out) + "\n"
    if path is not None:
        Path(path).write_text(svg, encoding="utf-8")
    return svg


def draw(ax, name_or_rings, *, glycerol="parallel", color="#222222", lw=1.2, ring_fill="none",
         fontsize=7, font_family=None, zorder=3):
    """Draw the molecule on a matplotlib Axes and fit the view to it.

    The Axes should have equal aspect (``ax.set_aspect("equal")``) and normally
    ``ax.axis("off")``. Returns the bounding box (xmin, ymin, xmax, ymax).
    """
    from matplotlib.patches import Polygon

    geo = geometry(name_or_rings, glycerol)
    for ring in geo["rings"]:
        ax.add_patch(Polygon(ring, closed=True, facecolor=ring_fill, edgecolor=color,
                             linewidth=lw, joinstyle="round", zorder=zorder))
    for line in geo["lines"]:
        ax.plot([p[0] for p in line], [p[1] for p in line], color=color, lw=lw,
                solid_capstyle="round", solid_joinstyle="round", zorder=zorder)
    text_kw = {"family": font_family} if font_family else {}
    for x, y, text in geo["labels"]:
        ax.text(x, y, text, color=color, fontsize=fontsize, ha="center", va="center",
                zorder=zorder + 1, **text_kw)
    x0, y0, x1, y1 = geo["bbox"]
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    return geo["bbox"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write GDGT skeletal structures as SVG files.")
    parser.add_argument("--outdir", default="figures/gdgt_structures", help="output folder")
    parser.add_argument("--names", nargs="*", default=list(GDGTS), help="which GDGTs to write")
    parser.add_argument("--glycerol", default="parallel", choices=("parallel", "antiparallel"))
    parser.add_argument("--scale", type=float, default=16.0, help="pixels per bond length")
    parser.add_argument("--color", default="#222222")
    parser.add_argument("--stroke-width", type=float, default=1.5)
    parser.add_argument("--ring-fill", default="none", help="fill color of the rings")
    parser.add_argument("--font-family", default="Helvetica, Arial, sans-serif")
    parser.add_argument("--font-size", type=float, default=None, help="atom-label size in pixels")
    args = parser.parse_args(argv)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for name in args.names:
        target = outdir / f"{name}.svg"
        to_svg(name, target, glycerol=args.glycerol, scale=args.scale, color=args.color,
               stroke_width=args.stroke_width, ring_fill=args.ring_fill,
               font_family=args.font_family, font_size=args.font_size)
        print("wrote", target)


if __name__ == "__main__":
    main()
