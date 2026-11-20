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

FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
)

def normalize(text):
    return re.sub(r"\s+", " ", text).strip()

def default_font():
    for name in FONTS:
        if Path(name).exists():
            return name
    raise RuntimeError("Install a Cyrillic TTF, e.g. fonts-dejavu-core")

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
                        "color": span["color"]
                    })
    return spans

def font_to_rgb(n):
    return ((n >> 16 & 255)/255, (n >> 8 & 255)/255, (n & 255)/255)

def process(original, positions_file, output, report_file, require_complete=False):
    positions = json.loads(Path(positions_file).read_text(encoding="utf-8"))
    doc = fitz.open(original)
    if doc.is_encrypted:
        raise RuntimeError("Encrypted PDF")
    font = default_font()
    f = fitz.Font(fontfile=font)
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
            width = fitz.Rect(sp["bbox"]).width * 1.05
            size = sp["size"]
            while size >= max(5.5, sp["size"]*.5) and f.text_length(target,fontsize=size)>width:
                size -= .25
            if not target or size < max(5.5,sp["size"]*.5):
                failures.append({"page":i+1,"source":source,
                                 "reason":"translation cannot fit original text box"})
                continue
            candidates.append((idx,sp,target,size))
            used.add(idx)
        # No filled white rectangle: preserve table shading and underlying artwork.
        for _, sp, _, _ in candidates:
            page.add_redact_annot(fitz.Rect(sp["bbox"]), fill=False, cross_out=False)
        if candidates:
            page.apply_redactions(images=0,graphics=0,text=0)
        for _, sp, target, size in candidates:
            page.insert_text(fitz.Point(sp["origin"]), target,
                             fontfile=font, fontname="Cyrillic", fontsize=size,
                             color=font_to_rgb(sp["color"]), overlay=True)
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
