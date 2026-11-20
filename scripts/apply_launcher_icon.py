#!/usr/bin/env python3
"""Use the supplied squared Gold Wing emblem as the Android launcher icon.

Run this after 'npx cap add android', because Capacitor creates Android
resource folders during that step.
"""
from pathlib import Path
from PIL import Image

SRC = Path("assets/gl1800_icon.webp")
if not SRC.exists():
    raise SystemExit(f"Missing launcher image: {SRC}")

icon = Image.open(SRC).convert("RGBA")
# Android launcher mipmap pixel sizes for the five standard densities.
densities = [
    ("mipmap-mdpi", 48),
    ("mipmap-hdpi", 72),
    ("mipmap-xhdpi", 96),
    ("mipmap-xxhdpi", 144),
    ("mipmap-xxxhdpi", 192),
]
for folder, size in densities:
    dest = Path("android/app/src/main/res") / folder
    dest.mkdir(parents=True, exist_ok=True)
    main = icon.resize((size, size), Image.Resampling.LANCZOS)
    # Legacy launchers display the squared-corner icon directly.
    main.save(dest / "ic_launcher.png")
    main.save(dest / "ic_launcher_round.png")
    # Adaptive icons need a central safe area; preserve the entire emblem.
    fg = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    side = round(size * 0.74)
    a = icon.resize((side, side), Image.Resampling.LANCZOS)
    fg.alpha_composite(a, ((size-side)//2, (size-side)//2))
    fg.save(dest / "ic_launcher_foreground.png")
print(f"Applied {SRC} at all 5 Android densities")
