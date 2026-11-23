#!/usr/bin/env python3
"""Fetch the verified Russian image manual from the owner's shared Google Drive ZIP."""
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

FILE_ID = "1qgcUc0OC7fTcSlU7ZNOBrykVeA4dSQJ7"
SHA256 = "e60885277359b18860f1b6c67f6e18418d5db0cd5cde6ec5278a65f0423a7c79"
root = Path("www")
archive = Path("/tmp/gl1800-ru-source.zip")
subprocess.run([sys.executable, "-m", "gdown", "--id", FILE_ID, "-O", str(archive)], check=True)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
if digest != SHA256:
    raise SystemExit(f"Unexpected Russian source archive checksum: {digest}")
with zipfile.ZipFile(archive) as z:
    names = z.namelist()
    if "www/data.js" not in names or not any(n.startswith("www/pages-") for n in names):
        raise SystemExit("Russian archive is incomplete")
    (root / "data.js").write_bytes(z.read("www/data.js"))
    for name in names:
        if name.startswith("www/pages-") and name.endswith(".zip"):
            with zipfile.ZipFile(z.open(name)) as pages:
                for item in pages.infolist():
                    if not item.filename.startswith("pages/") or not item.filename.endswith(".png"):
                        raise SystemExit(f"Unexpected path: {item.filename}")
                    dest = root / item.filename
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(pages.read(item))
count = len(list((root / "pages").glob("p[0-9][0-9][0-9].png")))
if count != 757:
    raise SystemExit(f"Expected 757 Russian page images, found {count}")
for n in range(1,758):
    if not (root / "pages" / f"p{n:03d}.png").is_file():
        raise SystemExit(f"Missing Russian page {n}")
print("PASS: 757 Russian PNG pages downloaded and packaged; no English manual PDF")
