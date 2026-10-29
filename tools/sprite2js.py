"""Turn a figure cut from a PNG into a marble sprite for marble-cascade.html.

    python3 tools/sprite2js.py NAME PNG X0 Y0 X1 Y1 HEIGHT [--flip] [--ink 0.35] [--levels]

Crops the box (X0, Y0)-(X1, Y1), trims it to the figure, scales it to HEIGHT pixels tall
(averaging, so heavy line art thins out cleanly) and maps each pixel by brightness onto the
marble ramp: k = ink outline, 0 = white, 1-3 = deeper cyan shade, '.' = clear (--levels first
spreads the figure's own brightness over the ramp by rank, for dark art like bronze statues). Prints a
JS line to paste into the SPRITES table. Needs no libraries: PNGs are decoded with zlib.
"""
import bisect, struct, sys, zlib


def read_png(path):
    data = open(path, 'rb').read()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', 'not a PNG'
    pos, idat, pal, trns = 8, b'', None, None
    while pos < len(data):
        n, kind = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b'IHDR':
            w, h, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB', body)
            assert depth == 8 and interlace == 0, 'only 8-bit, non-interlaced PNGs'
        elif kind == b'PLTE':
            pal = [tuple(body[i:i + 3]) for i in range(0, n, 3)]
        elif kind == b'tRNS':
            trns = body
        elif kind == b'IDAT':
            idat += body
    bpp = {6: 4, 2: 3, 3: 1, 0: 1, 4: 2}[ctype]
    raw, stride, prev, rows = zlib.decompress(idat), w * bpp, bytearray(w * bpp), []
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], prev[i - bpp] if i >= bpp else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line); prev = line
    def px(x, y):  # → (r, g, b, a)
        r = rows[y]
        if ctype == 6: return tuple(r[x * 4:x * 4 + 4])
        if ctype == 2: return (*r[x * 3:x * 3 + 3], 255)
        if ctype == 3:
            i = r[x]; return (*pal[i], trns[i] if trns and i < len(trns) else 255)
        if ctype == 0: return (r[x],) * 3 + (255,)
        return (r[x * 2],) * 3 + (r[x * 2 + 1],)
    return w, h, px


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flip, levels, ink = '--flip' in sys.argv, '--levels' in sys.argv, 0.35
    if '--ink' in sys.argv: ink = float(sys.argv[sys.argv.index('--ink') + 1]); args.remove(str(sys.argv[sys.argv.index('--ink') + 1]))
    name, path, x0, y0, x1, y1, height = args[0], args[1], *map(int, args[2:7])
    w, h, px = read_png(path)
    x1, y1 = min(x1, w), min(y1, h)
    # trim to the figure
    xs = [x for y in range(y0, y1) for x in range(x0, x1) if px(x, y)[3] > 40]
    ys = [y for y in range(y0, y1) for x in range(x0, x1) if px(x, y)[3] > 40]
    x0, x1, y0, y1 = min(xs), max(xs) + 1, min(ys), max(ys) + 1
    lums = [sum(c * f for c, f in zip(px(x, y)[:3], (.3, .59, .11))) / 255 for y in range(y0, y1) for x in range(x0, x1) if px(x, y)[3] > 40]
    ranks = sorted(lums)  # --levels: brightness by rank within the figure, so dark art spreads over the whole ramp
    norm = (lambda l: bisect.bisect_left(ranks, l) / len(ranks)) if levels else (lambda l: l)
    cut = .2 if levels else .3  # darker than this counts toward the outline
    k = (y1 - y0) / height
    out_w = max(1, round((x1 - x0) / k))
    out = []
    for oy in range(height):
        row = ''
        for ox in range(out_w):
            ax, bx, ay, by = x0 + int(ox * k), x0 + max(int(ox * k) + 1, int((ox + 1) * k)), y0 + int(oy * k), y0 + max(int(oy * k) + 1, int((oy + 1) * k))
            n = a = lum = dark = 0
            for y in range(ay, min(by, y1)):
                for x in range(ax, min(bx, x1)):
                    r, g, b, al = px(x, y); n += 1; a += al
                    if al > 40:
                        l = norm((r * .3 + g * .59 + b * .11) / 255); lum += l; dark += l < cut
            if not n or a / n < 90: row += '.'; continue
            solid = sum(1 for y in range(ay, min(by, y1)) for x in range(ax, min(bx, x1)) if px(x, y)[3] > 40)
            l = lum / solid
            row += 'k' if dark / solid > ink else '0' if l > .8 else '1' if l > .62 else '2' if l > .45 else '3'
        out.append(row[::-1] if flip else row)
    print(f"  {name}: [\n" + ''.join(f"    '{r}',\n" for r in out) + "  ],")


main()
