#!/usr/bin/env python3
"""Regression: GL1800 diagrams must never lose original technical labels."""
import json
import tempfile
from pathlib import Path
import fitz
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_russian_manual import generate

def test_preserve_diagram_text():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        original = root / "original.pdf"
        translations = root / "ru.json"
        localized = root / "ru.pdf"

        doc = fitz.open()
        p = doc.new_page(width=450, height=600)
        p.draw_rect(fitz.Rect(40, 80, 400, 240), color=(0, 0, 0))
        p.draw_line((45, 150), (390, 150), color=(0, 0, 0))
        p.insert_text((70, 115), "FRONT BRAKE", fontsize=11)
        p.insert_text((70, 185), "WIRE R/G", fontsize=11)
        p.insert_text((70, 270), "AIR CLEANER", fontsize=11)
        doc.save(original)
        doc.close()

        translations.write_text(json.dumps({"1": "Передний тормоз. Провод красно-зелёный."},
                                          ensure_ascii=False), encoding="utf-8")
        generate(str(original), str(translations), str(localized))

        with fitz.open(localized) as result:
            content = result[0].get_text()
            for label in ("FRONT BRAKE", "WIRE R/G", "AIR CLEANER"):
                assert label in content, f"Diagram lost technical label: {label}"
            assert "Передний тормоз" in content
        print("PASS: all original diagram and table captions retained")

if __name__ == "__main__":
    test_preserve_diagram_text()
