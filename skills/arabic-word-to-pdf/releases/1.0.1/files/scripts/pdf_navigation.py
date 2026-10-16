"""Build and verify human-readable lesson/topic outlines at Word's exact PDF destinations."""
from __future__ import annotations

from pypdf import PdfWriter
from pypdf.generic import Fit, NullObject


def walk_outline(items, depth=0):
    for item in items:
        if isinstance(item, list):
            yield from walk_outline(item, depth + 1)
        else:
            yield item, depth


def destination_spec(reader, destination, title, level):
    page = reader.get_destination_page_number(destination)
    if page is None or not 0 <= page < len(reader.pages):
        raise ValueError(f"Invalid outline destination: {title}")
    array = destination.dest_array
    args = [None if isinstance(v, NullObject) else float(v) for v in array[2:]]
    return {"title": title, "level": level, "page": page,
            "fit_type": str(array[1]), "fit_args": args}


def read_navigation(reader, row):
    native = list(walk_outline(reader.outline))
    navigation = row.get("navigation")
    if navigation is None:
        # Older manifests can still regenerate the combined PDF, preserving existing topic outlines.
        title = row.get("title") or row["pdf"].rsplit(".", 1)[0]
        specs = [{"title": title, "level": 0, "page": 0,
                  "fit_type": "/Fit", "fit_args": []}]
        specs += [destination_spec(reader, d, d.title, depth + 1) for d, depth in native]
        return specs
    lookup = dict(reader.named_destinations)
    lookup.update({d.title: d for d, _ in native})
    entries = [{"title": navigation["title"], "level": 0,
                "bookmark": navigation["bookmark"]}] + navigation["headings"]
    # On regeneration the individual PDFs already contain the finished human-readable outline.
    # Require the entire title sequence and hierarchy to match the saved plan before reusing it.
    final_outline = None
    if all(entry["bookmark"] not in lookup for entry in entries):
        levels = []
        expected_depths = []
        for entry in entries:
            while levels and levels[-1] >= int(entry["level"]):
                levels.pop()
            expected_depths.append(len(levels))
            levels.append(int(entry["level"]))
        if ([d.title for d, _ in native] == [entry["title"] for entry in entries]
                and [depth for _, depth in native] == expected_depths):
            final_outline = [d for d, _ in native]
    specs = []
    last_page = 0
    for index, entry in enumerate(entries):
        title = entry["title"].strip()
        level = int(entry["level"])
        if not title or not 0 <= level <= 9 or (specs and level == 0):
            raise ValueError(f"Invalid navigation heading: {entry}")
        bookmark = entry["bookmark"]
        if final_outline is None and bookmark not in lookup:
            raise ValueError(f"Word did not export heading destination: {row['source']} / {title}")
        destination = final_outline[index] if final_outline is not None else lookup[bookmark]
        spec = destination_spec(reader, destination, title, level)
        if spec["page"] < last_page:
            raise ValueError(f"Heading order changed: {title}")
        last_page = spec["page"]
        specs.append(spec)
    return specs


def add_navigation(writer, specs, offset=0, root_title=None):
    stack = []
    expected = []
    for index, spec in enumerate(specs):
        while stack and stack[-1][0] >= spec["level"]:
            stack.pop()
        title = root_title if index == 0 and root_title else spec["title"]
        depth = len(stack)
        ref = writer.add_outline_item(
            title, offset + spec["page"], parent=stack[-1][1] if stack else None,
            fit=Fit(spec["fit_type"], spec["fit_args"]),
            bold=index == 0, is_open=index == 0,
        )
        expected.append(dict(spec, title=title, depth=depth, page=offset + spec["page"]))
        stack.append((spec["level"], ref))
    writer.page_mode = "/UseOutlines"
    return expected


def verify_navigation(reader, expected):
    actual = list(walk_outline(reader.outline))
    if len(actual) != len(expected):
        raise ValueError("PDF outline heading count changed")
    for (dest, depth), wanted in zip(actual, expected):
        got = destination_spec(reader, dest, dest.title, wanted["level"])
        if (got["title"], got["page"], depth, got["fit_type"]) != (
                wanted["title"], wanted["page"], wanted["depth"], wanted["fit_type"]):
            raise ValueError(f"PDF outline hierarchy/destination mismatch: {wanted['title']}")
        if len(got["fit_args"]) != len(wanted["fit_args"]):
            raise ValueError(f"PDF outline destination coordinates missing: {wanted['title']}")
        for a, b in zip(got["fit_args"], wanted["fit_args"]):
            if (a is None) != (b is None) or (a is not None and abs(a - b) > 0.01):
                raise ValueError(f"PDF outline destination coordinates changed: {wanted['title']}")


def write_individual(reader, target, specs):
    """Keep the exported page contents intact; replace technical bookmark names with real titles."""
    import os
    import tempfile
    from pypdf import PdfReader

    writer = PdfWriter()
    writer.append(reader, import_outline=False)
    if reader.metadata:
        writer.add_metadata({key: str(value) for key, value in reader.metadata.items() if value is not None})
    expected = add_navigation(writer, specs)
    handle, temporary = tempfile.mkstemp(prefix=".navigation-", suffix=".pdf", dir=target.parent)
    os.close(handle)
    try:
        writer.write(temporary)
        writer.close()
        check = PdfReader(temporary, strict=True)
        if len(check.pages) != len(reader.pages):
            raise ValueError("Individual PDF navigation changed page count")
        for before, after in zip(reader.pages, check.pages):
            left, right = before.get_contents(), after.get_contents()
            if (left.get_data() if left else b"") != (right.get_data() if right else b""):
                raise ValueError("Individual PDF navigation changed page content")
        verify_navigation(check, expected)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
