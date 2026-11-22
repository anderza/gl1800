#!/usr/bin/env python3
"""Prevent distributing the English service manual as a Russian APK.

This is a release gate, NOT a translation tool. A text layer containing
Russian alongside English is not by itself proof of full localization.
"""
import re
import sys
from pathlib import Path

import fitz

def verify(path):
    document = fitz.open(path)
    if document.page_count != 757:
        raise SystemExit(f"Expected 757 pages; got {document.page_count}")
    deficient = []
    for i, page in enumerate(document):
        text = page.get_text("text")
        ru = len(re.findall(r"[А-Яа-яЁё]", text))
        en = len(re.findall(r"[A-Za-z]", text))
        # Part numbers, brand names and wire codes may legitimately remain Latin.
        # Require substantive Cyrillic on each substantive text page, and
        # avoid an English-dominant text layer (the previous failure mode).
        if en + ru > 120 and (ru < 80 or ru / (ru + en) < 0.55):
            deficient.append((i + 1, ru, en))
    if deficient:
        print("FAIL: manual is not fully localized. Examples (page, Cyrillic, Latin):")
        print(deficient[:20])
        raise SystemExit(f"Refusing to publish an English or mixed-language APK: {len(deficient)} pages failed")
    print(f"PASS: Cyrillic text coverage verified on {document.page_count} pages")
    print("NOTE: diagram/raster captions still require visual QA")

if __name__ == "__main__":
    verify(Path(sys.argv[1]))
