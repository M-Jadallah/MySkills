import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const job = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const previewMode = process.argv[3] === 'preview';
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(previewMode ? job.output_path : job.template_path));
const sheet = workbook.worksheets.getItemAt(0);
if (previewMode) {
  const previews = [];
  for (const [index, range] of job.preview_ranges.entries()) {
    const image = await workbook.render({ sheetName: sheet.name, range, scale: 1.5, format: 'png' });
    const target = path.join(job.work_dir, `preview-${index + 1}.png`);
    await fs.writeFile(target, new Uint8Array(await image.arrayBuffer()));
    previews.push(target);
  }
  await fs.writeFile(path.join(job.work_dir, 'preview-receipt.json'), JSON.stringify({ previews, preview_complete: true }), 'utf8');
} else {
  const currentHeaders = sheet.getRange('A1:K1').values[0];
  if (JSON.stringify(currentHeaders) !== JSON.stringify(job.headers)) throw new Error('Template columns changed');
  const last = job.rows.length + 1;
  sheet.getRange(`A2:K${Math.max(last, 1073)}`).clear({ applyTo: 'contents' });
  sheet.getRange(`A2:K${last}`).values = job.rows;
  sheet.getRange(`A1:K${last}`).format.rowHeight = 22;
  sheet.getRange(`C2:C${last}`).format.wrapText = true;
  for (let i = 0; i < job.rows.length; i++) {
    if (job.rows[i][6] === 1) sheet.getRange(`A${i + 2}:K${i + 2}`).format.autofitRows();
  }
  workbook.recalculate();
  const check = await workbook.inspect({ kind: 'table', range: `${sheet.name}!A1:K${Math.min(last, 12)}`, tableMaxRows: 12, tableMaxCols: 11, maxChars: 4000 });
  await fs.writeFile(path.join(job.work_dir, 'artifact-inspect.ndjson'), check.ndjson, 'utf8');
  await (await SpreadsheetFile.exportXlsx(workbook)).save(job.output_path);
  await fs.writeFile(path.join(job.work_dir, 'export-receipt.json'), JSON.stringify({ export_complete: true, output: job.output_path }), 'utf8');
}
