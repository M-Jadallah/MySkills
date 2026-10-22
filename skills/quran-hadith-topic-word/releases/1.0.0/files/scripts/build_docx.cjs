#!/usr/bin/env node
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const {validateData, witnessSpans} = require('./validate_data.cjs');
const args = process.argv.slice(2);
function arg(key) { const i = args.indexOf(key); return i < 0 ? undefined : args[i + 1]; }
const modules = arg('--modules');
let docx;
try { docx = require(require.resolve('docx', {paths: [modules, __dirname].filter(Boolean)})); }
catch { console.error('The docx Node package is required. Pass --modules with the workspace dependency package directory.'); process.exit(1); }
const {Document, Packer, Paragraph, TextRun, Footer, AlignmentType, BorderStyle, ShadingType, ExternalHyperlink, SimpleField} = docx;
const theme = JSON.parse(fs.readFileSync(path.join(__dirname, '../assets/design.json'), 'utf8'));
const FONT = {ascii: theme.font, hAnsi: theme.font, eastAsia: theme.font, cs: theme.font};
function run(text, options = {}) {
  const {citation = false, relation = false, ...rest} = options;
  if (citation) text = text.replace(/[\r\n\t]+/g, ' ');
  const size = 2 * (citation ? theme.citation_pt : relation ? theme.relation_pt : theme.body_pt);
  return new TextRun({text, font: FONT, size, sizeComplexScript: size, color: citation ? theme.colors.citation : theme.colors.text,
    rightToLeft: true, language: {value: 'ar-SA', bidirectional: 'ar-SA'}, ...rest});
}
function paragraph(children, style, extra = {}) {
  return new Paragraph({style, children, bidirectional: true, alignment: AlignmentType.START,
    widowControl: true, ...extra});
}
function orderParagraphBorders(xml) {
  if (!xml || typeof xml !== 'object') return;
  if (Array.isArray(xml)) { xml.forEach(orderParagraphBorders); return; }
  const order = ['w:top', 'w:left', 'w:bottom', 'w:right', 'w:between', 'w:bar'];
  for (const [key, value] of Object.entries(xml)) {
    if (key === 'w:pBdr' && Array.isArray(value)) {
      value.sort((a, b) => order.indexOf(Object.keys(a)[0]) - order.indexOf(Object.keys(b)[0]));
    }
    orderParagraphBorders(value);
  }
}
function citationFor(item, includeRelations = true) {
  const children = [];
  const add = text => children.push(run(text, {citation: true}));
  const link = (source, label = source.reference) => children.push(new ExternalHyperlink({link: source.url, children: [run(label, {citation: true})]}));
  if (item.type === 'quran') {
    const number = item.ayah_number.toString().replace(/\d/g, n => '٠١٢٣٤٥٦٧٨٩'[n]);
    link(item.source, `سورة ${item.surah_name}، الآية ${number}.`);
  } else {
    add('المصدر: '); link(item.source);
    const grade = {sahih: 'صحيح', hasan: 'حسن', disputed: 'مختلف في صحته'}[item.status];
    add(` | الحكم: ${grade}.`);
    for (const j of item.judgments) {
      add('؛ ');
      link(j.source, `${j.scholar}: ${j.ruling}`);
      if (j.basis !== 'collection') add(`؛ محل الحكم: ${j.scope}`);
      // The original reference already identifies this exact linked source.
      if (j.source.url !== item.source.url) { add(' ('); link(j.source); add(')'); }
    }
    if (item.dispute_explanation) add(` | بيان محل الحكم: ${item.dispute_explanation}`);
  }
  if (includeRelations && item.relation.source) { add(' | مرجع وجه الارتباط: '); link(item.relation.source); }
  return paragraph(children, 'Citation');
}
function quoteParagraph(item) {
  const spans = witnessSpans(item.text, item.witnesses);
  const children = [run(item.type === 'quran' ? '﴿' : '(', {color: theme.colors.evidence})];
  let cursor = 0;
  for (const span of spans) {
    if (span.start > cursor) children.push(run(item.text.slice(cursor, span.start), {color: theme.colors.evidence}));
    children.push(run(item.text.slice(span.start, span.end), {color: theme.colors.witness, bold: theme.witness_bold, boldComplexScript: theme.witness_bold}));
    cursor = span.end;
  }
  if (cursor < item.text.length) children.push(run(item.text.slice(cursor), {color: theme.colors.evidence}));
  children.push(run(item.type === 'quran' ? '﴾' : ')', {color: theme.colors.evidence}));
  return paragraph(children, 'Evidence');
}
function build(data, template = false, options = {}) {
  const includeRelations = options.includeRelations !== false;
  if (!template) validateData(data);
  const children = [paragraph([run(data.topic, {bold: true, boldComplexScript: true})], 'Title', {alignment: AlignmentType.CENTER})];
  if (template) {
    children.push(paragraph([run('عنوان المحور', {bold: true, boldComplexScript: true})], 'Heading1'));
    children.push(paragraph([run('قال تعالى أو مقدمة رواية الحديث هنا:')], 'Intro'));
    children.push(paragraph([run('يوضع هنا نص الآية أو متن الحديث كاملًا.', {color: theme.colors.evidence})], 'Evidence'));
    children.push(paragraph([run('التوثيق هنا بخط Traditional Arabic وحجم 16 نقطة.', {citation: true})], 'Citation'));
    children.push(paragraph([run('وجه الارتباط: يكتب هنا في النسخة المشروحة فقط، بحجم 18 نقطة.', {relation: true})], 'Relation'));
  } else {
    if (data.scope_note) children.push(paragraph([run(data.scope_note)], 'Normal'));
    for (const section of data.sections) {
      children.push(paragraph([run(section.title, {bold: true, boldComplexScript: true})], 'Heading1',
        {indent: {end: section.title.length > 38 ? 0 : 3200}}));
      const ordered = [...section.evidence.filter(x => x.type === 'quran'), ...section.evidence.filter(x => x.type === 'hadith')];
      for (const item of ordered) {
        children.push(paragraph([run(item.type === 'quran' ? 'قال تعالى:' : item.intro)], 'Intro'));
        children.push(quoteParagraph(item));
        children.push(citationFor(item, includeRelations));
        if (includeRelations) {
          const relationLead = item.relation.type === 'indirect' ? 'وجه الارتباط غير المباشر: ' : 'وجه الارتباط: ';
          children.push(paragraph([run(relationLead + item.relation.text, {relation: true})], 'Relation'));
        }
      }
    }
  }
  const bodyRun = {font: FONT, size: theme.body_pt * 2, sizeComplexScript: theme.body_pt * 2,
    color: theme.colors.text, rightToLeft: true, language: {value: 'ar-SA', bidirectional: 'ar-SA'}};
  // Logical START is the right edge in RTL; physical RIGHT is mirrored by Word/LibreOffice here.
  const baseP = {bidirectional: true, alignment: AlignmentType.START, spacing: {line: theme.line_spacing, before: 0, after: 100}, widowControl: true};
  const style = (id, name, p = {}, r = {}) => ({id, name, basedOn: id === 'Normal' ? undefined : 'Normal', next: 'Normal', quickFormat: true,
    run: {...bodyRun, ...r}, paragraph: {...baseP, ...p}});
  const titleStyle = style('Title', 'Title', {alignment: AlignmentType.CENTER, keepNext: true, spacing: {before: 120, after: 260, line: 360},
        shading: {fill: theme.colors.title_fill, type: ShadingType.CLEAR},
        border: {top: {color: theme.colors.evidence, size: theme.title_line_size, style: BorderStyle.SINGLE, space: 10}}},
        {bold: true, boldComplexScript: true});
  const headingStyle = style('Heading1', 'Heading 1', {outlineLevel: 0, keepNext: true, spacing: {before: 160, after: 130, line: 300},
        border: {bottom: {color: theme.colors.evidence, size: theme.heading_line_size, style: BorderStyle.SINGLE, space: 5}}},
        {bold: true, boldComplexScript: true});
  const document = new Document({creator: 'Quran Hadith Topic Word', title: data.topic, description: 'أدلة قرآنية وحديثية موثقة حسب الموضوع',
    styles: {default: {document: {run: bodyRun, paragraph: baseP}, title: titleStyle, heading1: headingStyle,
      ...Object.fromEntries([2,3,4,5,6].map(n => ['heading'+n, {run: {...bodyRun, bold: true, boldComplexScript: true}, paragraph: {...baseP, outlineLevel: n-1, keepNext: true}}])),
      hyperlink: {run: {...bodyRun, size: theme.citation_pt*2, sizeComplexScript: theme.citation_pt*2, color: theme.colors.citation}}
    }, paragraphStyles: [
      style('Normal', 'Normal'),
      style('Intro', 'مقدمة الدليل', {keepNext: true, spacing: {before: 40, after: 40, line: theme.line_spacing}}),
      style('Evidence', 'نص الدليل', {spacing: {before: 100, after: 160, line: theme.line_spacing}, indent: {start: 140, end: 140},
        shading: {fill: theme.colors.evidence_fill, type: ShadingType.CLEAR},
        border: Object.fromEntries(['top','left','bottom','right'].map(edge => [edge, {color: theme.colors.evidence_border, size: 4, style: BorderStyle.SINGLE, space: 8}]))}),
      style('Citation', 'التوثيق', {spacing: {before: 0, after: 30, line: 240}}, {size: theme.citation_pt * 2, sizeComplexScript: theme.citation_pt * 2, color: theme.colors.citation}),
      style('Footer', 'ترقيم الصفحة', {}, {size: theme.citation_pt * 2, sizeComplexScript: theme.citation_pt * 2}),
      style('Relation', 'وجه الارتباط', {spacing: {before: 70, after: 150, line: theme.line_spacing}}, {size: theme.relation_pt*2, sizeComplexScript: theme.relation_pt*2})
    ]},
    sections: [{properties: {page: {size: {width: theme.page.width, height: theme.page.height}, margin: {
      top: theme.page.top, bottom: theme.page.bottom, left: theme.page.left, right: theme.page.right, header: 360, footer: 360}}},
      footers: {default: new Footer({children: [paragraph([new SimpleField('PAGE \\* Arabic', '1')], 'Footer', {alignment: AlignmentType.CENTER})]})}, children}]
  });
  // Normalize the serialized public styles tree: some docx versions emit bottom before left,
  // whereas OOXML CT_PBdr requires top, left, bottom, right, between, bar.
  const prepareStyles = document.Styles.prepForXml.bind(document.Styles);
  document.Styles.prepForXml = context => {
    const xml = prepareStyles(context);
    orderParagraphBorders(xml);
    return xml;
  };
  return document;
}
async function main() {
  const output = arg('--output');
  if (!output || (!args.includes('--template') && !arg('--input'))) throw new Error('Usage: node build_docx.cjs --input INPUT.json --output WITH_RELATIONS.docx [--output-without-relations WITHOUT_RELATIONS.docx] [--modules PATH]\nOr: --template --output TEMPLATE.docx');
  const template = args.includes('--template');
  const data = template ? {topic: 'عنوان الموضوع'} : JSON.parse(fs.readFileSync(arg('--input'), 'utf8').replace(/^\uFEFF/, ''));
  const outputs = [{path: path.resolve(output), includeRelations: true}];
  if (!template) {
    const parsed = path.parse(output);
    const without = arg('--output-without-relations') || path.join(parsed.dir, parsed.name + '-بدون-وجه-الارتباط.docx');
    outputs.push({path: path.resolve(without), includeRelations: false});
  }
  if (new Set(outputs.map(o => process.platform === 'win32' ? o.path.toLowerCase() : o.path)).size !== outputs.length) throw new Error('The two output paths must be different');
  for (const entry of outputs) {
    if (path.extname(entry.path).toLowerCase() !== '.docx') throw new Error('Output files must use the .docx extension');
    if (fs.existsSync(entry.path) && !args.includes('--overwrite')) throw new Error('Output already exists; use another name or explicit --overwrite: ' + entry.path);
  }
  if (!template) validateData(data);
  for (const entry of outputs) {
    const document = build(data, template, {includeRelations: entry.includeRelations});
    fs.mkdirSync(path.dirname(entry.path), {recursive: true});
    fs.writeFileSync(entry.path, await Packer.toBuffer(document));
  }
  console.log(JSON.stringify({outputs, template}));
}
if (require.main === module) main().catch(error => {console.error(error.stack || error.message); process.exitCode = 1;});
module.exports = {build};
