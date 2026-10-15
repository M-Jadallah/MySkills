#!/usr/bin/env python3
"""Chem Spectrum Lab - Logo generator.

Renders the "مختبر الطيف للكيمياء" logo as PNG in two variants:
  - logo.png      (light background use)
  - logo-dark.png (dark background use)
A flask with a colored spectrum wave, plus the lab name and teacher line.

Usage:
    python make_logo.py --out "<frontend>/assets"
Requires: pip install pillow cairosvg   (cairosvg optional; we use Pillow+SVG raster)
"""
import argparse, pathlib, sys, io

SKILL = pathlib.Path(__file__).resolve().parent.parent

# Brand colors
PRIMARY = (0, 212, 255)
SECONDARY = (26, 35, 126)
WHITE = (255, 255, 255)


def svg_logo(dark=False):
    """Return an SVG string for the logo. dark=True => transparent/white ink."""
    ink = "#FFFFFF" if dark else "#1A237E"
    wave = "#00D4FF"
    flask = "#00D4FF" if dark else "#1A237E"
    bg = "none"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="200" viewBox="0 0 480 200">
  <rect width="480" height="200" fill="{bg}"/>
  <g transform="translate(20,30)">
    <!-- flask -->
    <path d="M40 10 h40 v30 l34 76 a14 14 0 0 1 -12 21 H18 a14 14 0 0 1 -12 -21 l34 -76 Z"
          fill="none" stroke="{flask}" stroke-width="6"/>
    <line x1="20" y1="60" x2="100" y2="60" stroke="{flask}" stroke-width="5"/>
    <!-- spectrum wave -->
    <path d="M10 130 q20 -40 40 0 t40 0 t40 0 t40 0" fill="none" stroke="{wave}" stroke-width="6" opacity="0.9"/>
    <circle cx="20" cy="130" r="5" fill="{wave}"/>
    <circle cx="100" cy="130" r="5" fill="{wave}"/>
  </g>
  <text x="150" y="80" font-family="Noto Kufi Arabic, Arial" font-size="30" font-weight="700" fill="{ink}">مختبر الطيف</text>
  <text x="150" y="115" font-family="Noto Kufi Arabic, Arial" font-size="20" fill="{wave}">للكيمياء</text>
  <text x="150" y="150" font-family="Arial" font-size="14" fill="{ink}" opacity="0.8">م. معتصم جادالله — مدرس كيمياء</text>
</svg>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="assets/ folder to write logo.png + logo-dark.png")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    try:
        import cairosvg  # noqa
        for dark, name in ((False, "logo.png"), (True, "logo-dark.png")):
            cairosvg.svg2png(bytestring=svg_logo(dark).encode("utf-8"),
                             write_to=str(out / name), output_width=480, output_height=200)
        print("Logo written (cairosvg):", out / "logo.png", out / "logo-dark.png")
    except Exception:
        # Pillow fallback: render a simple placeholder (flask glyph) so the file exists
        from PIL import Image, ImageDraw
        for dark, name in ((False, "logo.png"), (True, "logo-dark.png")):
            img = Image.new("RGBA", (480, 200), (0, 0, 0, 0) if dark else (245, 247, 250, 255))
            d = ImageDraw.Draw(img)
            d.line([(40, 30), (140, 30), (170, 150)], fill=PRIMARY if dark else SECONDARY, width=6)
            d.line([(20, 60), (190, 60)], fill=PRIMARY if dark else SECONDARY, width=5)
            d.ellipse([(30, 140), (190, 170)], outline=PRIMARY, width=4)
            img.save(out / name)
        print("Logo written (Pillow fallback):", out / "logo.png", out / "logo-dark.png")
        print("NOTE: install cairosvg for full SVG-quality logo: pip install cairosvg")


if __name__ == "__main__":
    main()
