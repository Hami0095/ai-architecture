"""Builds the deployable site into site/: the website at / and the MkDocs docs at /docs/.

    python scripts/build_site.py            # build
    python scripts/build_site.py --serve    # build, then serve on http://127.0.0.1:8000

Vercel runs this through `npm run build` (see package.json and vercel.json).
"""
import argparse
import functools
import http.server
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def build():
    shutil.rmtree(SITE, ignore_errors=True)
    shutil.copytree(ROOT / "website", SITE, ignore=shutil.ignore_patterns("demo", "sheet.html", "README.md"))
    subprocess.run([sys.executable, "-m", "mkdocs", "build", "--strict", "-q", "-d", str(SITE / "docs")],
                   cwd=ROOT, check=True)
    print(f"built {SITE.relative_to(ROOT)}/ (website at /, docs at /docs/)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8000)
    opts = parser.parse_args()
    build()
    if opts.serve:
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
        print(f"serving http://127.0.0.1:{opts.port}/  (Ctrl+C to stop)")
        http.server.ThreadingHTTPServer(("127.0.0.1", opts.port), handler).serve_forever()


if __name__ == "__main__":
    main()
