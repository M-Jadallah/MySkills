#!/usr/bin/env python3
"""Chem Spectrum Lab - Orchestrator runtime.

Dependency-aware, SEQUENTIAL sub-agent pipeline (each agent hands off to the
next) to minimize the orchestrator's context window.

  Agent 1 (step 01): PDF  -> canonical lesson-XX.md  [SEQUENTIAL gate]
  Agent 2 (step 02): md   -> design-XX.md            [parallel-safe with 05/06]
  Agent 5 (step 05): md   -> pptx + print pdf         (parallel with 02/06)
  Agent 6 (step 06): md   -> docx                     (parallel with 02/05)
  Agent 3 (step 03): design -> standalone lab (inherits ../../shared)
  Agent 4 (step 04): lab  -> integrated site (registers lesson, wires nav)

Each step is dispatched as its own sub-agent via delegate_task; the orchestrator
only coordinates. This file is the LOCAL harness that mirrors that order and
places the production Docker files. In the live run, spawn agents per phase.

Usage:
    python run_pipeline.py --pdf "<path>/lesson.pdf" --lesson 03 --root "<path>/chem-spectrum-lab"
"""
import argparse, pathlib, shutil, subprocess, sys

SKILL = pathlib.Path(__file__).resolve().parent.parent
DOCKER_REF = SKILL / "references" / "docker"
STEPS = SKILL.parent  # skills/ root

# Maps step -> (skill dir name, script)
AGENTS = {
    "01": ("chem-spectrum-lab-01-pdf-to-md", "scripts/extract_pdf.py"),
    "03": ("chem-spectrum-lab-03-lab-build", "scripts/scaffold.py"),
    "04": ("chem-spectrum-lab-04-integration", "scripts/scaffold.py"),
}


def ensure_deps():
    try:
        import fitz, pptx, docx, arabic_reshaper, bidi, matplotlib, reportlab  # noqa
    except ImportError:
        print("MISSING DEPS. Run: pip install pymupdf python-pptx python-docx "
              "arabic-reshaper python-bidi matplotlib reportlab")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--lesson", required=True, help="Lesson number, e.g. 03")
    ap.add_argument("--root", required=True, help="chem-spectrum-lab/ repo root")
    args = ap.parse_args()
    ensure_deps()

    root = pathlib.Path(args.root)
    XX = args.lesson.zfill(2)
    # step 01 writes <pdf_dir>/<stem>/lesson-XX.md ; we standardize here:
    stem = pathlib.Path(args.pdf).stem
    work = root / "frontend" / "lessons" / f"lesson-{XX}"
    src = work / "_src"; src.mkdir(parents=True, exist_ok=True)
    md = src / f"lesson-{XX}.md"

    # Phase 0: tree
    for d in (root/"frontend"/"shared", root/"docker", root/"backend", root/"database",
              work/"assets", work/"css", work/"js"):
        d.mkdir(parents=True, exist_ok=True)

    print("=== PHASE 1 [AGENT 01]: PDF -> lesson-XX.md ===")
    helper = STEPS / AGENTS["01"][0] / AGENTS["01"][1]
    # step 01 writes into <pdf_dir>/<stem>/ (its own output convention)
    pdf_dir = pathlib.Path(args.pdf).parent
    subprocess.run([sys.executable, str(helper), args.pdf, "--xx", XX],
                   cwd=str(pdf_dir), check=True)
    # step 01 output: <pdf_dir>/<stem>/lesson-XX.md
    produced = pdf_dir / stem / f"lesson-{XX}.md"
    if produced.exists():
        shutil.copy(produced, md)
        # also copy extracted assets (images/pages) into the lesson _src
        for sub in ("images", "pages"):
            src_sub = pdf_dir / stem / sub
            if src_sub.exists():
                shutil.copytree(src_sub, src / sub, dirs_exist_ok=True)
        print(f"  [01] canonical Markdown ready: {md}")
    else:
        print("  [01] WARNING: lesson-XX.md not found; agent must produce it.")

    print("=== PHASE 2 [AGENTS 02/05/06 in parallel]: design + pptx + docx ===")
    print("  spawn sub-agents reading", md)
    print("   [02] -> design-XX.md")
    print("   [05] -> lesson-XX.pptx + lesson-XX-print.pdf")
    print("   [06] -> lesson-XX.docx")

    print("=== PHASE 3 [AGENT 03 then 04]: build lab -> integrate ===")
    print(f"  [03] scaffold frontend/lessons/lesson-{XX}/ (inherits ../../shared)")
    print(f"  [04] register lesson-{XX} in integrated site (wires nav.js)")

    print("=== PHASE 4: animation hardening (desktop epic) ===")
    shutil.copy(SKILL/"references"/"device.js", root/"frontend"/"shared"/"device.js")
    shutil.copy(SKILL/"references"/"fx.js", root/"frontend"/"shared"/"fx.js")
    print("  copied shared/device.js + shared/fx.js")

    print("=== PHASE 5: assemble docker/ for Coolify ===")
    for f in ("docker-compose.yml", "Dockerfile.frontend", "nginx.conf"):
        shutil.copy(DOCKER_REF / f, root / "docker" / f)
    print(f"  docker/ ready: {[p.name for p in (root/'docker').iterdir()]}")

    print("\nDONE. Commit & push, then Coolify -> Docker Compose build pack.")
    print("Verify: docker compose -f docker/docker-compose.yml build")


if __name__ == "__main__":
    main()
