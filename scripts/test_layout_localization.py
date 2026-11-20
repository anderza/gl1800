#!/usr/bin/env python3
"""Check that geometry and vector graphics survive in-place RU replacements."""
import json
import tempfile
from pathlib import Path
import fitz
from localize_pdf_in_place import process
from extract_layout_spans import run

def main():
    with tempfile.TemporaryDirectory() as t:
        d=Path(t)
        src=d/"original.pdf"; dest=d/"russian.pdf"; template=d/"positions.json"
        report=d/"report.json"
        doc=fitz.open()
        page=doc.new_page(width=612,height=792)
        page.draw_rect(fitz.Rect(30,50,570,160),color=(.2,.2,.2),fill=(.93,.94,.94))
        page.draw_line((30,105),(570,105),color=(.2,.2,.2))
        page.draw_line((290,50),(290,160),color=(.2,.2,.2))
        page.insert_text((50,85),"Engine Oil",fontsize=16)
        page.insert_text((310,85),"Replace",fontsize=16)
        page.draw_circle((240,360),radius=100,color=(0,0,1))
        page.insert_text((250,390),"Figure Label",fontsize=13)
        doc.save(src);doc.close()
        run(src,template)
        labels=json.loads(template.read_text(encoding="utf-8"))
        translated={"Engine Oil":"Моторное масло",
                    "Replace":"Заменить",
                    "Figure Label":"Подпись рисунка"}
        for item in labels["1"]:
            item["ru"]=translated[item["source"]]
        template.write_text(json.dumps(labels,ensure_ascii=False),encoding="utf-8")
        result=process(src,template,dest,report,require_complete=True)
        assert result["completed"]
        a,b=fitz.open(src),fitz.open(dest)
        assert a[0].rect==b[0].rect
        assert len(a[0].get_drawings())==len(b[0].get_drawings())
        final=b[0].get_text()
        for en,ru in translated.items():
            assert en not in final
            assert ru in final
        print("PASS: Russian text in table/figure positions; page geometry unchanged")

if __name__=="__main__":
    main()
