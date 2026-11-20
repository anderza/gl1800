#!/usr/bin/env python3
"""Create a per-position translation template from the ORIGINAL PDF.

Every source text span has its own page number and precise bounding rectangle.
Captions rasterized into image pixels cannot be extracted by PDF text APIs and
must be annotated manually before localization.
"""
import argparse
import json
from pathlib import Path
import fitz

def run(src,dest):
    doc=fitz.open(src)
    result={}
    for num,page in enumerate(doc,1):
        entries=[]
        for block in page.get_text("dict")["blocks"]:
            if block["type"]!=0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text=span["text"].strip()
                    if text:
                        entries.append({"source":text,"ru":"",
                                        "bbox":[round(v,2) for v in span["bbox"]]})
        result[str(num)]=entries
    dest=Path(dest)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=1),encoding="utf-8")
    print("Prepared %d pages and %d source labels" %
          (len(result),sum(map(len,result.values()))))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("original")
    p.add_argument("output")
    a=p.parse_args()
    run(a.original,a.output)
