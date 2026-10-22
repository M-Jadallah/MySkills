#!/usr/bin/env node
'use strict';
const fs = require('node:fs');

function need(value, message) { if (!value) throw new Error(message); }
function nonempty(value) { return typeof value === 'string' && value.trim().length > 0; }
function sourceOK(source, at) {
  need(source && nonempty(source.reference), `${at}: missing source.reference`);
  need(source.checked === true, `${at}: source.checked must record a completed source review`);
  let url;
  try { url = new URL(source.url); } catch { throw new Error(`${at}: source.url is invalid`); }
  need(['https:', 'http:'].includes(url.protocol), `${at}: only http(s) source links are supported`);
}
function witnessSpans(text, witnesses) {
  need(Array.isArray(witnesses) && witnesses.length > 0, 'At least one exact witness quotation is required');
  const spans = witnesses.map(item => {
    const quote = typeof item === 'string' ? item : item?.quote;
    need(nonempty(quote), 'Witness must have nonempty quote');
    const starts = [];
    let pos = 0;
    while (pos <= text.length - quote.length) {
      const found = text.indexOf(quote, pos);
      if (found < 0) break;
      starts.push(found);
      pos = found + quote.length;
    }
    need(starts.length > 0, `Witness does not match exact source text: ${quote}`);
    const occurrence = typeof item === 'object' ? item.occurrence : undefined;
    need(starts.length === 1 || occurrence !== undefined, `Repeated witness requires occurrence: ${quote}`);
    const index = occurrence ?? 1;
    need(Number.isInteger(index) && index > 0 && index <= starts.length, 'Witness occurrence is out of range');
    const start = starts[index - 1], end = start + quote.length;
    need(!/\p{M}/u.test(text[start]) && !(end < text.length && /\p{M}/u.test(text[end])), 'Witness splits an Arabic combining-mark cluster');
    return { start, end, quote };
  }).sort((a, b) => a.start - b.start);
  for (let i = 1; i < spans.length; i++) need(spans[i].start >= spans[i - 1].end, 'Witness ranges overlap');
  return spans;
}
function evidenceList(data) { return data.sections.flatMap(section => section.evidence); }
function validateData(data) {
  need(data && nonempty(data.topic), 'topic is required');
  need(Array.isArray(data.sections) && data.sections.length > 0, 'sections is required');
  const ids = new Set();
  for (const [si, section] of data.sections.entries()) {
    need(nonempty(section.title), `section ${si + 1}: title is required`);
    need(Array.isArray(section.evidence) && section.evidence.length > 0, `section ${si + 1}: evidence is required`);
    for (const item of section.evidence) {
      const at = item.id || `section ${si + 1}`;
      need(nonempty(item.id) && !ids.has(item.id), `${at}: duplicate or missing id`); ids.add(item.id);
      need(['quran', 'hadith'].includes(item.type), `${at}: unsupported evidence type`);
      need(nonempty(item.text), `${at}: complete text is required`);
      need(!/[﴿﴾]/u.test(item.text), `${at}: supply text without Quran brackets`);
      need(!/(?:\.{3}|…|إلى آخره)/u.test(item.text), `${at}: truncated evidence is not allowed`);
      need(item.full_text_verified === true, `${at}: full_text_verified must record completed source comparison`);
      sourceOK(item.source, at);
      witnessSpans(item.text, item.witnesses);
      need(item.relation && ['direct', 'indirect'].includes(item.relation.type) && nonempty(item.relation.text), `${at}: relation type and text are required`);
      if (item.relation.source) sourceOK(item.relation.source, `${at} relation`);
      if (item.type === 'quran') {
        need(nonempty(item.surah_name), `${at}: surah_name is required`);
        need(Number.isInteger(item.surah_number) && item.surah_number >= 1 && item.surah_number <= 114, `${at}: invalid surah_number`);
        need(Number.isInteger(item.ayah_number) && item.ayah_number >= 1 && item.ayah_number <= 286, `${at}: invalid ayah_number`);
      } else {
        need(nonempty(item.narrator), `${at}: narrator is required`);
        need(nonempty(item.intro) && item.intro.includes(item.narrator), `${at}: intro must include narrator`);
        need(['sahih', 'hasan', 'disputed'].includes(item.status), `${at}: only sahih, hasan or disputed hadiths are allowed`);
        need(Array.isArray(item.judgments) && item.judgments.length > 0, `${at}: sourced judgments are required`);
        for (const judgment of item.judgments) {
          need(nonempty(judgment.scholar) && nonempty(judgment.ruling) && nonempty(judgment.scope), `${at}: scholar, ruling and scope are required`);
          need(['accept', 'weaken'].includes(judgment.side), `${at}: judgment side must be accept or weaken`);
          need(['explicit', 'collection'].includes(judgment.basis), `${at}: judgment basis must be explicit or collection`);
          if (judgment.basis === 'collection') need(judgment.side === 'accept', `${at}: collection basis cannot be a weakening judgment`);
          sourceOK(judgment.source, `${at} judgment`);
        }
        need(item.judgments.some(j => j.side === 'accept'), `${at}: a documented acceptance judgment is required`);
        if (item.status === 'disputed') {
          need(item.judgments.some(j => j.side === 'weaken'), `${at}: disputed hadith requires a documented weakening judgment`);
          need(nonempty(item.dispute_explanation), `${at}: explain the actual scope of disagreement`);
        } else if (item.judgments.some(j => j.side === 'weaken')) {
          need(nonempty(item.dispute_explanation), `${at}: explain why a weakening judgment does not change the overall status`);
        }
      }
    }
  }
  return {sections: data.sections.length, evidence: evidenceList(data).length};
}
if (require.main === module) {
  try {
    need(process.argv[2], 'Usage: node validate_data.cjs INPUT.json');
    const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8').replace(/^\uFEFF/, ''));
    console.log(JSON.stringify({valid: true, ...validateData(data)}));
  } catch (error) { console.error(error.message); process.exitCode = 1; }
}
module.exports = {validateData, witnessSpans, evidenceList};
