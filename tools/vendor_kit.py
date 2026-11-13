"""Copy the design-system files this page uses from one pinned release, unedited, and write the adoption pin.

Every copied file must match its sha256 in the release manifest, or nothing is written.
Usage: python3 -I -B tools/vendor_kit.py <version> [<design system folder>]
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = sys.argv[1]
REL = Path(sys.argv[2]).resolve() / "releases" / VERSION if len(sys.argv) > 2 else ROOT.parent / "viz-design-system" / "releases" / VERSION
FILES = ["tokens.css", "tokens.json", "kit/kit.css", "kit/kit.js", "kit/numfmt.py", "kit/takeaway.css", "kit/takeaway.js",
         "kit/wayfinding.css", "kit/wayfinding.js", "assets/fonts/public-sans-latin-400-normal.woff2",
         "assets/fonts/public-sans-latin-600-normal.woff2", "assets/fonts/ibm-plex-mono-latin-400-normal.woff2",
         "assets/fonts/ibm-plex-mono-latin-500-normal.woff2", "assets/fonts/newsreader-latin-500-normal.woff2",
         "assets/fonts/newsreader-latin-600-normal.woff2", "assets/fonts/newsreader.LICENSE.txt",
         "assets/fonts/public-sans.LICENSE.txt", "assets/fonts/ibm-plex-mono.LICENSE.txt", "assets/fonts/manifest.json",
         "LICENSE", "THIRD_PARTY_NOTICES.md"]

manifest_bytes = (REL / "release-manifest.json").read_bytes()
manifest = json.loads(manifest_bytes)
pinned = {f["path"]: f for f in manifest["files"]}
entries = []
for rel in FILES:
    data = (REL / rel).read_bytes()
    h = hashlib.sha256(data).hexdigest()
    assert rel in pinned and pinned[rel]["sha256"] == h, f"{rel} does not match the {VERSION} release manifest"
    entries.append((rel, data, h))
for rel, data, h in entries:
    dst = ROOT / "vendor" / "viz-design-system" / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
pin = {"dependency": "viz-design-system", "version": VERSION, "status_at_adoption": manifest["status"],
       "release_id": manifest["release_id"], "manifest_path": f"portfolio/viz-design-system/releases/{VERSION}/release-manifest.json",
       "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(), "payload_sha256": manifest["payload_sha256"],
       "copied_from": f"releases/{VERSION} only; bytes unedited", "previous_pin": None,
       "files": [{"path": f"vendor/viz-design-system/{rel}", "release_path": rel, "bytes": len(data), "sha256": h}
                 for rel, data, h in entries]}
(ROOT / "vendor" / "viz-design-system-adoption.json").write_text(json.dumps(pin, indent=1) + "\n", encoding="utf-8")
print(f"vendored {len(entries)} files from {VERSION}, all matching the release manifest")
