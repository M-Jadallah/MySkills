"""CLI for offline student Quran plans with the preserved Excel template."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import posixpath
import re
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
import zipfile

from planner import CATALOG_PATH, PlanError, build_plan

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
MAIN_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS = {'s': MAIN_NS}


def read_xlsx(file):
    with zipfile.ZipFile(file) as archive:
        if archive.testzip() is not None:
            raise PlanError('invalid_xlsx_zip')
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        sheets = list(workbook.find('s:sheets', NS))
        if len(sheets) != 1:
            raise PlanError('template_sheet_count_changed')
        relationships = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        relid = sheets[0].attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        target = next(r.attrib['Target'] for r in relationships if r.attrib['Id'] == relid)
        sheet_path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
        root = ET.fromstring(archive.read(sheet_path))
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared_root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
            shared = [''.join(t.text or '' for t in si.iter(f'{{{MAIN_NS}}}t')) for si in shared_root]
        rows = []
        for row in root.find('s:sheetData', NS):
            values = [None] * 11
            for cell in row:
                if cell.find('s:f', NS) is not None or cell.attrib.get('t') == 'e':
                    raise PlanError(f'unexpected_formula_or_error: {cell.attrib.get("r")}')
                column = re.match(r'[A-Z]+', cell.attrib['r'])[0]
                index = 0
                for letter in column:
                    index = index * 26 + ord(letter) - 64
                v = cell.find('s:v', NS)
                inline = cell.find('s:is', NS)
                if v is None and inline is None:
                    continue
                if index > 11:
                    raise PlanError('extra_output_column')
                kind = cell.attrib.get('t')
                if kind == 's':
                    value = shared[int(v.text)]
                elif kind == 'inlineStr':
                    value = ''.join(t.text or '' for t in inline.iter(f'{{{MAIN_NS}}}t'))
                elif kind == 'b':
                    value = v.text == '1'
                elif kind == 'str':
                    value = v.text or ''
                else:
                    number = float(v.text)
                    value = int(number) if number.is_integer() else number
                values[index - 1] = value
            if any(v is not None for v in values):
                rows.append(values)
        return {'rows': rows, 'sheet_name': sheets[0].attrib['name'], 'root': root, 'sheet_path': sheet_path}


def finish_native_metadata(output, template, expected_last_row):
    original = read_xlsx(template)['root'].find('s:sheetViews/s:sheetView', NS)
    temporary = output.with_name(output.name + '.native.tmp')
    with zipfile.ZipFile(output) as source, zipfile.ZipFile(temporary, 'w') as target:
        for entry in source.infolist():
            contents = source.read(entry.filename)
            if entry.filename == 'xl/worksheets/sheet1.xml':
                root = ET.fromstring(contents)
                root.find('s:sheetViews/s:sheetView', NS).attrib.update(original.attrib)
                data = root.find('s:sheetData', NS)
                for row in list(data):
                    if int(row.attrib['r']) > expected_last_row:
                        if any(len(cell) for cell in row):
                            raise PlanError('unexpected_trailing_data')
                        data.remove(row)
                dimension = root.find('s:dimension', NS)
                if dimension is not None:
                    dimension.set('ref', f'A1:K{expected_last_row}')
                ET.register_namespace('x', MAIN_NS)
                contents = ET.tostring(root, encoding='utf-8', xml_declaration=True)
            target.writestr(entry, contents)
    os.replace(temporary, output)


def verify_file(output, payload, template):
    actual = read_xlsx(output)
    reference = read_xlsx(template)
    if actual['rows'] != [payload['headers']] + payload['rows']:
        raise PlanError('export_values_changed: القيم أو الأعمدة المصدرة لا تطابق الخطة')
    if actual['sheet_name'] != reference['sheet_name']:
        raise PlanError('sheet_name_changed')
    view = actual['root'].find('s:sheetViews/s:sheetView', NS)
    if view.attrib.get('rightToLeft') not in ('1', 'true'):
        raise PlanError('rtl_lost')
    if not all(row[0] is None and row[1] == i for i, row in enumerate(actual['rows'][1:], 1)):
        raise PlanError('id_or_sort_order_invalid')
    return True


def module_link(work_dir, dependencies):
    link = work_dir / 'node_modules'
    if link.exists():
        if link.resolve() != dependencies.resolve():
            raise PlanError('unexpected_node_modules_target')
        return
    if os.name == 'nt':
        literal = lambda p: "'" + str(p).replace("'", "''") + "'"
        command = f'New-Item -ItemType Junction -Path {literal(link)} -Target {literal(dependencies)} | Out-Null'
        encoded = base64.b64encode(command.encode('utf-16le')).decode('ascii')
        subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded], check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        link.symlink_to(dependencies, target_is_directory=True)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def build_workbook(spec, output_dir, work_dir, node, modules, preview=True, overwrite=False):
    payload = build_plan(spec)
    output_dir, work_dir = pathlib.Path(output_dir).resolve(), pathlib.Path(work_dir).resolve()
    output = output_dir / payload['filename']
    if output.exists() and not overwrite:
        raise PlanError('output_exists: استخدم مجلد إخراج جديدًا مع الإبقاء على اسم الطالب')
    if output.resolve().parent != output_dir:
        raise PlanError('output_path_escape')
    node, modules = pathlib.Path(node).resolve(), pathlib.Path(modules).resolve()
    if not node.is_file() or not modules.is_dir():
        raise PlanError('runtime_missing: مرر مسارات Node وnode_modules من load_workspace_dependencies')
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    module_link(work_dir, modules)
    renderer = work_dir / 'render_workbook.mjs'
    shutil.copyfile(SKILL_DIR / 'scripts/render_workbook.mjs', renderer)
    template = SKILL_DIR / 'assets/plan-template.xlsx'
    before_hash = hashlib.sha256(template.read_bytes()).hexdigest()
    last = len(payload['rows']) + 1
    preview_ranges = [f'A1:K{min(last, 20)}']
    if last > 20:
        preview_ranges.append(f'A{max(2, last - 12)}:K{last}')
    job = {**payload, 'template_path': str(template), 'output_path': str(output), 'work_dir': str(work_dir), 'preview_ranges': preview_ranges}
    job_path = work_dir / 'job.json'
    write_json(job_path, job)
    receipt_path = work_dir / 'export-receipt.json'
    receipt_path.unlink(missing_ok=True)
    run = subprocess.run([str(node), str(renderer), str(job_path)], capture_output=True, text=True, encoding='utf-8', errors='replace')
    (work_dir / 'export-process.log').write_text(run.stdout + run.stderr, encoding='utf-8')
    if not receipt_path.exists() or not json.loads(receipt_path.read_text())['export_complete'] or not output.exists():
        raise PlanError(f'export_failed: {run.stderr or run.stdout}')
    finish_native_metadata(output, template, last)
    verify_file(output, payload, template)
    if hashlib.sha256(template.read_bytes()).hexdigest() != before_hash:
        raise PlanError('template_modified')
    previews = []
    preview_exit = None
    if preview:
        receipt_path = work_dir / 'preview-receipt.json'
        receipt_path.unlink(missing_ok=True)
        rendering = subprocess.run([str(node), str(renderer), str(job_path), 'preview'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        preview_exit = rendering.returncode
        (work_dir / 'preview-process.log').write_text(rendering.stdout + rendering.stderr, encoding='utf-8')
        if not receipt_path.exists():
            raise PlanError(f'preview_failed: {rendering.stderr or rendering.stdout}')
        receipt = json.loads(receipt_path.read_text())
        previews = receipt.get('previews', [])
        if not receipt.get('preview_complete') or not previews or any(not pathlib.Path(p).read_bytes().startswith(b'\x89PNG\r\n\x1a\n') for p in previews):
            raise PlanError('preview_failed: لم تُنتج صور PNG صالحة')
    sidecar = output.with_name(output.name + '.inspect.ndjson')
    if sidecar.exists():
        shutil.move(str(sidecar), str(work_dir / 'export-inspect.ndjson'))
    report = {'output': str(output), 'filename': payload['filename'], 'verified': True, 'id_empty': True, **payload['summary'], 'notices': payload['notices'], 'previews': previews, 'work_dir': str(work_dir), 'export_engine_exit_code': run.returncode, 'preview_engine_exit_code': preview_exit}
    write_json(work_dir / 'verification.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description='خطة قرآن تراكمية باسم الطالب وبالقالب الأصلي؛ id فارغ.')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('lookup')
    data_parser = commands.add_parser('plan')
    data_parser.add_argument('--spec', required=True)
    build_parser = commands.add_parser('build')
    build_parser.add_argument('--spec', required=True)
    build_parser.add_argument('--out-dir', required=True)
    build_parser.add_argument('--work-dir')
    build_parser.add_argument('--node', required=True)
    build_parser.add_argument('--node-modules', required=True)
    build_parser.add_argument('--no-preview', action='store_true')
    build_parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'lookup':
            catalog = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
            result = {key: [{field: row[field] for field in ('number', 'name', 'first_page', 'last_page')} for row in catalog[key]] for key in ('surahs', 'juzs')}
        else:
            spec = json.loads(pathlib.Path(args.spec).read_text(encoding='utf-8-sig'))
            if args.command == 'plan':
                result = build_plan(spec)
            else:
                work_dir = args.work_dir or str(pathlib.Path(args.out_dir).parent / ('.quran-work-' + uuid.uuid4().hex[:12]))
                result = build_workbook(spec, args.out_dir, work_dir, args.node, args.node_modules, not args.no_preview, args.overwrite)
        print(json.dumps(result, ensure_ascii=False))
    except (PlanError, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
