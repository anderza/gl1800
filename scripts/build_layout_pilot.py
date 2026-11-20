#!/usr/bin/env python3
"""Generate an inspectable, exact-dimensions translation pilot for pages 3 and 7.

This deliberately does NOT replace the released APK: the other 755 pages
and any labels rasterized into the diagrams still need localization and QA.
"""
import argparse
import json
from pathlib import Path
import fitz
from extract_layout_spans import run
from localize_pdf_in_place import process

def main(src,translations,outdir):
    dest=Path(outdir);dest.mkdir(parents=True,exist_ok=True)
    source=fitz.open(src)
    pilot=fitz.open()
    for idx in [2,6]:
        pilot.insert_pdf(source,from_page=idx,to_page=idx)
    original=dest/"original-pages-3-and-7.pdf"
    pilot.save(original)
    pilot.close()
    source.close()
    template=dest/"extracted_positions.json"
    run(original,template)
    labels=json.loads(template.read_text(encoding="utf-8"))
    translations=json.loads(Path(translations).read_text(encoding="utf-8"))
    for localpage,originalpage in [("1","3"),("2","7")]:
        phrases=translations[originalpage]
        found=set()
        for entry in labels[localpage]:
            source_text=entry["source"]
            if source_text not in phrases:
                continue
            entry["ru"]=phrases[source_text]
            found.add(source_text)
            x=entry["bbox"][0]
            if originalpage=="7" and 130<=x<270:
                entry["available_width"]=145
            elif originalpage=="7" and 292<=x<350:
                entry["available_width"]=244
            elif originalpage=="3" and x>=129:
                entry["available_width"]=max(20,550-x)
            elif originalpage=="3" and x<100:
                entry["available_width"]=520
            elif originalpage=="7" and x<60:
                entry["available_width"]=290 if entry["bbox"][1]<200 else 180
            elif originalpage=="7" and 140<=x<200:
                entry["available_width"]=120
        missing=set(phrases)-found
        if missing:
            raise ValueError("Translation map has phrases absent from page %s: %s"%(originalpage,sorted(missing)))
        labels[localpage]=[entry for entry in labels[localpage] if entry.get("ru")]
    positions=dest/"mapped_ru_positions.json"
    positions.write_text(json.dumps(labels,ensure_ascii=False,indent=2),encoding="utf-8")
    output=dest/"GL1800-RU-layout-pilot.pdf"
    report=process(original,positions,output,dest/"pilot_report.json")
    print("PILOT QUALITY:",json.dumps(report["statistics"],ensure_ascii=False),flush=True)
    print("UNFITTED SPANS:",json.dumps(report["failures"],ensure_ascii=False),flush=True)
    doc=fitz.open(output)
    for idx,original_num in enumerate([3,7]):
        doc[idx].get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(dest/("page-%d.png"%original_num))
    doc.close()
    if report["failures"]:
        raise RuntimeError("Unfitted labels; correct the coordinate map before release")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("original")
    p.add_argument("translation_map")
    p.add_argument("output_dir")
    a=p.parse_args()
    main(a.original,a.translation_map,a.output_dir)
