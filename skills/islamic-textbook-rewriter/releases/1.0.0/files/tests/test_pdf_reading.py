"""Real PDF fixtures exercise text/scans, batch coverage and source identity."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pymupdf as fitz
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from prepare_pdf import parse_crop, parse_pages, prepare_pdf
from verify_pdf_review import verify_review


@pytest.fixture
def mixed_pdf(tmp_path):
    path = tmp_path / "mixed-book.pdf"
    with fitz.open() as document:
        first = document.new_page(width=300, height=400)
        first.insert_text((25, 40), "Textbook lesson: definitions, examples and an activity.")
        png = first.get_pixmap(dpi=120).tobytes("png")
        scanned = document.new_page(width=300, height=400)
        scanned.insert_image(scanned.rect, stream=png)
        last = document.new_page(width=300, height=400)
        last.insert_text((25, 40), "Third page continues the lesson.")
        last.set_rotation(90)
        document.save(path)
    return path


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_text_and_image_only_pages_both_render(mixed_pdf, tmp_path):
    report = prepare_pdf(mixed_pdf, tmp_path / "reading", dpi=96)
    assert report["ok"] and not report["visual_review_complete"]
    manifest = read(report["manifest"])
    assert len(manifest["pages"]) == 3
    assert manifest["pages"][0]["text_characters"] > 0
    assert manifest["pages"][1]["text_layer_status"] == "none"
    assert Path(manifest["pages"][1]["text_path"]).read_text() == ""
    assert manifest["pages"][2]["rotation"] == 90
    assert manifest["pages"][2]["width_px"] > manifest["pages"][2]["height_px"]
    assert all(Path(row["image_path"]).is_file() and row["visual_reading_required"] for row in manifest["pages"])
    assert all(row["status"] == "pending" for row in read(report["review_log"])["pages"])
    assert not verify_review(report["manifest"], report["review_log"])["ok"]


def test_batches_preserve_previous_pages_and_review_record(mixed_pdf, tmp_path):
    folder = tmp_path / "reading"
    first = prepare_pdf(mixed_pdf, folder, pages="١", dpi=96)
    review = read(first["review_log"])
    review["pages"][0]["status"] = "reviewed"
    Path(first["review_log"]).write_text(json.dumps(review), encoding="utf-8")
    second = prepare_pdf(mixed_pdf, folder, pages="٢-٣", dpi=96)
    assert second["rendered_full_pages"] == [1, 2, 3]
    assert read(second["review_log"])["pages"][0]["status"] == "reviewed"
    assert verify_review(second["manifest"], second["review_log"], pages="١")["ok"]
    result = verify_review(second["manifest"], second["review_log"])
    assert not result["ok"]
    assert [row["pdf_page"] for row in result["unresolved_pages"]] == [2, 3]


def test_crop_does_not_count_as_a_complete_page(mixed_pdf, tmp_path):
    report = prepare_pdf(mixed_pdf, tmp_path / "reading", pages="٢", crop="٠,٠.٥,١,١", dpi=96)
    manifest = read(report["manifest"])
    assert manifest["pages"] == []
    assert len(manifest["crops"]) == 1
    assert Path(manifest["crops"][0]["image_path"]).exists()
    result = verify_review(report["manifest"], report["review_log"], pages="٢")
    assert result["missing_images"] == [2]


def test_changed_pdf_cannot_mix_with_previous_batch(mixed_pdf, tmp_path):
    folder = tmp_path / "reading"
    report = prepare_pdf(mixed_pdf, folder, pages="1", dpi=96)
    with mixed_pdf.open("ab") as stream:
        stream.write(b"\n% changed source\n")
    with pytest.raises(ValueError, match="نسخة PDF أخرى"):
        prepare_pdf(mixed_pdf, folder, pages="2", dpi=96)
    assert not verify_review(report["manifest"], report["review_log"])["ok"]


def test_reviewed_status_needs_existing_full_image(mixed_pdf, tmp_path):
    report = prepare_pdf(mixed_pdf, tmp_path / "reading", dpi=96)
    review = read(report["review_log"])
    for row in review["pages"]:
        row["status"] = "reviewed"
    Path(report["review_log"]).write_text(json.dumps(review), encoding="utf-8")
    assert verify_review(report["manifest"], report["review_log"])["ok"]
    manifest = read(report["manifest"])
    Path(manifest["pages"][1]["image_path"]).unlink()
    assert verify_review(report["manifest"], report["review_log"])["missing_images"] == [2]


@pytest.mark.parametrize("spec", ["0", "4", "3-1", "1-9999999", "", "one"])
def test_page_ranges_reject_missing_or_invalid_pages(spec):
    with pytest.raises(ValueError):
        parse_pages(spec, 3)


def test_arabic_ranges_and_crop_coordinates():
    assert parse_pages("١،٣–٥", 5) == [1, 3, 4, 5]
    assert parse_crop("٠,٠.٥,١,١") == (0, 0.5, 1, 1)
    with pytest.raises(ValueError):
        parse_crop("0,0,2,1")


def test_discovery_accepts_pdf_and_txt_directly(tmp_path):
    pdf = tmp_path / "book.PDF"
    pdf.write_bytes(b"discovery checks paths only")
    (tmp_path / "lesson.txt").write_text("lesson", encoding="utf-8")
    (tmp_path / "output.docx").write_bytes(b"exclude generated output")
    script = ROOT / "scripts" / "orchestrator.py"
    result = subprocess.run([sys.executable, str(script), str(tmp_path)], capture_output=True, text=True, encoding="utf-8", check=True)
    report = json.loads(result.stdout)
    assert {item["format"] for item in report["inputs"]} == {"txt", "pdf"}
    direct = subprocess.run([sys.executable, str(script), str(pdf)], capture_output=True, text=True, encoding="utf-8", check=True)
    assert json.loads(direct.stdout)["inputs"][0]["reading_mode"] == "page_images_and_text"
