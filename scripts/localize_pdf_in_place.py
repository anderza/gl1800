#!/usr/bin/env python3
"""Layout-safe Russian PDF text replacement.

Input: exact-position translations. Preserve original page size, tables,
figures, vector paths and images. Never distribute a supposedly finished
translation until the QA report has zero gaps and raster captions are checked.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path
import fitz

FONTS = {
    "regular": ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    "bold": ("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    "condensed": ("/usr/share/fonts/truetype/noto/NotoSans-Condensed.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"),
    "condensed_bold": ("/usr/share/fonts/truetype/noto/NotoSans-CondensedBold.ttf",
                       "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"),
}

def normalize(text):
    return re.sub(r"\s+", " ", text).strip()

def font_resources():
    result = {}
    for style, options in FONTS.items():
        name = next((path for path in options if Path(path).is_file()), None)
        if not name:
            raise RuntimeError("Cyrillic fonts missing: install fonts-noto-core")
        result[style] = (name, fitz.Font(fontfile=name))
    return result

def fits(value, font, size, width):
    return font.text_length(value, fontsize=size) <= width + 0.001

def fit_label(entry, source, fonts, width):
    text = normalize(entry.get("ru", ""))
    if not text:
        return None
    bold = bool(entry.get("bold", "Bold" in source["font"] or "Black" in source["font"]))
    regular = "bold" if bold else "regular"
    narrow = "condensed_bold" if bold else "condensed"
    size = source["size"]
    styles = (narrow, regular) if entry.get("prefer_condensed") else (regular, narrow)
    for style in styles:
        if fits(text, fonts[style][1], size, width):
            return style, size
    minimum = max(7.0, size * .8)
    while size >= minimum:
        if fits(text, fonts[narrow][1], size, width):
            return narrow, size
        size -= .2
    return None

def extract_spans(page):
    spans = []
    for block in page.get_text("dict").get("blocks", []):
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                source = normalize(span["text"])
                if source:
                    spans.append({
                        "text": source, "bbox": list(span["bbox"]),
                        "origin": list(span["origin"]), "size": span["size"],
                        "color": span["color"], "font": span["font"],
                        "ascender": float(span.get("ascender", .75)),
                        "descender": float(span.get("descender", -.22))
                    })
    return spans

def font_to_rgb(n):
    return ((n >> 16 & 255)/255, (n >> 8 & 255)/255, (n & 255)/255)

def process(original, positions_file, output, report_file, require_complete=False):
    positions = json.loads(Path(positions_file).read_text(encoding="utf-8"))
    doc = fitz.open(original)
    if doc.is_encrypted:
        raise RuntimeError("Encrypted PDF")
    fonts = font_resources()
    failures, summary = [], Counter()
    page_report = []
    for i, page in enumerate(doc):
        key = str(i+1)
        originals = extract_spans(page)
        row = positions.get(key, [])
        used = set()
        candidates = []
        for entry in row:
            source = normalize(entry["source"])
            matching = [(idx, sp) for idx, sp in enumerate(originals)
                        if normalize(sp["text"]) == source and idx not in used]
            if "bbox" in entry:
                wanted = fitz.Rect(entry["bbox"])
                matching = [(idx, sp) for idx, sp in matching
                            if sum(abs(a-b) for a,b in zip(wanted, sp["bbox"])) < 7]
            if len(matching) != 1:
                failures.append({"page":i+1,"source":source,
                                 "reason":"ambiguous or absent source text"})
                continue
            idx, sp = matching[0]
            target = normalize(entry.get("ru",""))
            left, baseline = sp["origin"]
            width = max(fitz.Rect(sp["bbox"]).width * 1.04,
                        float(entry.get("available_width", 0)))
            width = min(width, page.rect.x1 - left - 2)
            # Keep each label within its table column or illustration callout.
            same_line = [other["origin"][0] - left - 5
                         for oid, other in enumerate(originals)
                         if oid != idx and other["origin"][0] > left + 3
                         and abs(other["origin"][1] - baseline) < 2]
            if same_line:
                width = min(width, min(same_line))
            cell = entry.get("cell_bbox")
            if cell:
                cell = fitz.Rect(cell)
                width = min(cell.width - 4, page.rect.width - 4)
            choice = fit_label(entry, sp, fonts, width)
            if choice is None:
                failures.append({"page":i+1,"source":source,
                                 "reason":"Russian text cannot fit its table cell / line"})
                continue
            style, size = choice
            target = normalize(entry["ru"])
            face = fonts[style][1]
            if cell and entry.get("align") == "center":
                x = cell.x0 + (cell.width - face.text_length(target, fontsize=size)) / 2
            elif cell and entry.get("align") == "right":
                x = cell.x1 - face.text_length(target, fontsize=size) - 2
            else:
                x = left
            # Align the visual line centre despite different font ascenders.
            baseline += ((face.ascender + face.descender) -
                         (sp["ascender"] + sp["descender"])) * size / 2
            candidates.append((idx, sp, target, style, size, x, baseline))
            used.add(idx)
        # No filled white rectangle: preserve table shading and underlying artwork.
        for _, sp, *_ in candidates:
            page.add_redact_annot(fitz.Rect(sp["bbox"]), fill=False, cross_out=False)
        if candidates:
            page.apply_redactions(images=0,graphics=0,text=0)
        for _, sp, target, style, size, x, baseline in candidates:
            font_path, _ = fonts[style]
            page.insert_text(fitz.Point(x, baseline), target,
                             fontfile=font_path,
                             fontname="RULabel" + style.title().replace("_", ""),
                             fontsize=size, color=font_to_rgb(sp["color"]), overlay=True)
        untranslated = [sp["text"] for idx,sp in enumerate(originals)
                        if idx not in used and re.search(r"[A-Za-z]{3}",sp["text"])]
        summary["replaced"] += len(candidates)
        summary["untranslated_spans"] += len(untranslated)
        summary["pages"] += 1
        if row or i<3:
            page_report.append({"page":i+1,"replaced":len(candidates),
                                "untranslated_count":len(untranslated),
                                "untranslated_examples":untranslated[:15]})
    report={"statistics":dict(summary),"failures":failures,"per_page":page_report,
            "completed":summary["untranslated_spans"]==0 and not failures,
            "note":"Raster text inside images still requires manual image localization/QC"}
    Path(report_file).parent.mkdir(parents=True,exist_ok=True)
    Path(report_file).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if require_complete and not report["completed"]:
        raise RuntimeError("Untranslated spans: %d, failed mappings: %d. Report: %s" %
                           (summary["untranslated_spans"],len(failures),report_file))
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    doc.save(str(output),garbage=4,deflate=True)
    doc.close()
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("original")
    p.add_argument("positions_json")
    p.add_argument("output")
    p.add_argument("--report",default="layout_qa_report.json")
    p.add_argument("--require-complete",action="store_true")
    a=p.parse_args()
    print(json.dumps(process(a.original,a.positions_json,a.output,a.report,a.require_complete)["statistics"],ensure_ascii=False))
