#!/usr/bin/env python3
"""Build a Russian-first service manual, one PDF page per source page.

The original selectable English text is removed. Original pictures, vector
drawings and diagrams are preserved. Russian page text comes from the reviewed
translation_ru.json dataset.

This is a first-pass page reconstruction: translated paragraphs do not yet
follow the original typesetting or translated callout coordinates. Embedded
English lettering in raster drawings needs separate artwork localization.
"""
import argparse
import json
from pathlib import Path
import fitz

REGULAR = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
)
BOLD = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
)

def find_font(options):
    for filename in options:
        if Path(filename).is_file():
            return filename
    raise RuntimeError("Cyrillic font missing: install fonts-dejavu-core")

def wrap_lines(content, font, size, width):
    lines = []
    for para in content.replace("\r", "").split("\n"):
        para = para.strip()
        if not para:
            lines.append("")
            continue
        line = ""
        for word in para.split():
            candidate = word if not line else line + " " + word
            if font.text_length(candidate, fontsize=size) <= width:
                line = candidate
                continue
            if line:
                lines.append(line)
            line = ""
            for ch in word:
                if font.text_length(line + ch, fontsize=size) > width and line:
                    lines.append(line)
                    line = ch
                else:
                    line += ch
        if line:
            lines.append(line)
    while lines and not lines[-1]:
        lines.pop()
    return lines

def has_illustrations(page):
    # Some line art is composed of hundreds of vector paths, not image objects.
    try:
        return bool(page.get_image_info()) or len(page.get_drawings()) >= 8
    except Exception:
        return True

def strip_selectable_english(page):
    count = 0
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if not span.get("text", "").strip():
                    continue
                rect = fitz.Rect(span["bbox"]) & page.rect
                if rect.is_empty or rect.width < 1 or rect.height < 1:
                    continue
                page.add_redact_annot(rect, fill=(1, 1, 1), cross_out=False)
                count += 1
    if count:
        # Keep every image and vector drawing; remove only selectable text.
        page.apply_redactions(images=0, graphics=0, text=0)
    return count

def generate(original, translations_file, output):
    translations = json.loads(Path(translations_file).read_text(encoding="utf-8"))
    source = fitz.open(original)
    if source.is_encrypted:
        raise RuntimeError("Original PDF is encrypted")
    missing = [i for i in range(1, source.page_count + 1)
               if not str(translations.get(str(i), "")).strip()]
    if missing:
        raise RuntimeError(f"Russian translation missing for pages: {missing[:15]}")
    regfile, boldfile = find_font(REGULAR), find_font(BOLD)
    font = fitz.Font(fontfile=regfile)
    target = fitz.open()
    figures = 0
    for idx, page in enumerate(source):
        num = idx + 1
        text = str(translations[str(num)]).strip()
        art = has_illustrations(page)
        strip_selectable_english(page)

        width = max(420, page.rect.width)
        margin = min(39, width * .066)
        size, spacing = 16, 22.8
        lines = wrap_lines(text, font, size, width - margin * 2)
        text_h = max(35, len(lines) * spacing)
        art_h = page.rect.height if art else 0
        paper_h = 74 + text_h + (42 + art_h if art else 0) + 32

        dst = target.new_page(width=width, height=paper_h)
        dst.insert_font(fontname="Russian", fontfile=regfile)
        dst.insert_font(fontname="RussianBold", fontfile=boldfile)
        dst.draw_rect(fitz.Rect(0, 0, width, 40), fill=(.065, .105, .155), color=None)
        dst.insert_text((margin, 27), "GL1800  •  РУССКОЕ РУКОВОДСТВО",
                        fontsize=11, fontname="RussianBold", color=(1, 1, 1))
        dst.insert_text((width - margin - 67, 27), f"{num}/{source.page_count}",
                        fontsize=10, fontname="Russian", color=(1, 1, 1))
        baseline = 68 + size
        for line in lines:
            if line:
                dst.insert_text((margin, baseline), line, fontsize=size,
                                fontname="Russian", color=(.09, .11, .14))
            baseline += spacing
        if art:
            figures += 1
            top = 74 + text_h + 28
            dst.draw_line((margin, top - 23), (width - margin, top - 23),
                          color=(.75, .78, .81))
            dst.show_pdf_page(fitz.Rect(0, top, width, top + art_h),
                              source, idx, keep_proportion=False)
        if num % 50 == 0:
            print(f"Prepared {num}/{source.page_count} Russian pages", flush=True)

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    target.set_metadata({"title": "Honda GL1800 — Сервисное руководство на русском языке"})
    target.save(str(output), garbage=3, deflate=True)
    target.close()
    source.close()
    print(f"Russian pages: {len(translations)}, preserved artwork pages: {figures}", flush=True)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("original")
    p.add_argument("translations")
    p.add_argument("output")
    args = p.parse_args()
    generate(args.original, args.translations, args.output)
