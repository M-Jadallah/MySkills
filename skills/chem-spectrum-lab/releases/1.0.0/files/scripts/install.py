#!/usr/bin/env python3
"""Chem Spectrum Lab — one-command installer.

Run by ANY Hermes user to install the full 7-skill pipeline locally:
    python install.py

It:
  * copies the 7 skills (chem-spectrum-lab + 01..06) into the user's
    ~/.hermes/skills/chem-spectrum-lab/  (single parent keeps them grouped),
  * installs Python deps (pymupdf, python-pptx, python-docx, arabic-reshaper,
    python-bidi, matplotlib, reportlab, pillow [+cairosvg optional]),
  * generates the brand logo into the orchestrator's assets,
  * runs a self-check on every skill's frontmatter + helper scripts.

No network beyond pip. Idempotent: safe to re-run.
"""
import pathlib, shutil, subprocess, sys, json

# Where THIS installer lives == the orchestrator skill dir
ORCH = pathlib.Path(__file__).resolve().parent
SKILLS_ROOT = ORCH.parent  # .../skills/
TARGET = pathlib.Path.home() / ".hermes" / "skills" / "chem-spectrum-lab"

SKILL_NAMES = [
    "chem-spectrum-lab",
    "chem-spectrum-lab-01-pdf-to-md",
    "chem-spectrum-lab-02-interactive-design",
    "chem-spectrum-lab-03-lab-build",
    "chem-spectrum-lab-04-integration",
    "chem-spectrum-lab-05-powerpoint",
    "chem-spectrum-lab-06-word",
]

PIP_PKGS = ["pymupdf", "python-pptx", "python-docx", "arabic-reshaper",
            "python-bidi", "matplotlib", "reportlab", "pillow", "cairosvg"]


def copy_skills():
    copied = []
    for name in SKILL_NAMES:
        src = SKILLS_ROOT / name
        if not src.exists():
            print(f"  ! missing source skill: {name} (skip)")
            continue
        dst = TARGET / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        copied.append(name)
    return copied


def install_deps():
    print("  installing python deps (this may take a minute)...")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", *PIP_PKGS],
                       capture_output=True, text=True)
    return r.returncode == 0, r.stderr[:300] if r.returncode else ""


def make_logo():
    try:
        assets = TARGET / "chem-spectrum-lab" / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([sys.executable,
                            str(TARGET / "chem-spectrum-lab" / "scripts" / "make_logo.py"),
                            "--out", str(assets)], capture_output=True, text=True)
        return r.returncode == 0, r.stderr[:200] if r.returncode else r.stdout.strip()
    except Exception as e:
        return False, str(e)


def self_check():
    import yaml, re
    problems = []
    for name in SKILL_NAMES:
        sk = TARGET / name / "SKILL.md"
        if not sk.exists():
            problems.append(f"{name}: SKILL.md missing")
            continue
        txt = sk.read_text(encoding="utf-8")
        if not txt.startswith("---"):
            problems.append(f"{name}: bad frontmatter start")
            continue
        m = re.search(r"\n---\s*\n", txt[3:])
        if not m:
            problems.append(f"{name}: no closing ---")
            continue
        fm = yaml.safe_load(txt[3:m.start()+3])
        d = fm.get("description", "")
        if not (0 < len(d) <= 60 and d.endswith(".")):
            problems.append(f"{name}: description violated ({len(d)} chars)")
    return problems


def main():
    print("=== Chem Spectrum Lab — installer ===")
    print(f"Target: {TARGET}")
    print("[1/4] Copying 7 skills...")
    copied = copy_skills()
    print(f"      copied {len(copied)}/{len(SKILL_NAMES)} skills")

    print("[2/4] Installing dependencies...")
    ok, err = install_deps()
    print("      deps:", "OK" if ok else f"FAILED ({err})")

    print("[3/4] Generating brand logo...")
    lok, lmsg = make_logo()
    print("      logo:", "OK" if lok else f"note: {lmsg}")

    print("[4/4] Self-check...")
    problems = self_check()
    if problems:
        print("      PROBLEMS:")
        for p in problems:
            print("       -", p)
    else:
        print("      all 7 skills valid.")

    print("\nDONE. Restart your Hermes session, then say:")
    print('  "شغّل مختبر الطيف لدرس <رقم> من ملف <path>.pdf"')
    print("Skills will load from:", TARGET)


if __name__ == "__main__":
    main()
