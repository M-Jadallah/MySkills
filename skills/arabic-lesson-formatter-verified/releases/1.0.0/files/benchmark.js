'use strict';
const fs=require('fs'),path=require('path'),e=require('./engine');
const source=JSON.parse(fs.readFileSync(process.argv[2],'utf8').replace(/^\uFEFF/,''));const d=e.prepare(source,{hash:source.sourceHash});
const p=d.paragraphs.filter(p=>p.runs?.length>2).sort((a,b)=>JSON.stringify(b).length-JSON.stringify(a).length)[0];if(!p)throw Error('sample needs paragraph with several runs');
const bytes=x=>JSON.stringify(x).length;const r=p.runs.find(r=>r.text.length>5),r2=p.runs.find(x=>x!==r&&x.text.length>5);
const old=(runs)=>[{op:'update',id:p.id,expected:e.digest(p),value:{runs}}];
let changed=structuredClone(p.runs);changed.find(x=>x.id===r.id).text+=' '; // neutral edit for measuring payload only
const newer=[{op:'run-text',id:p.id,runId:r.id,expected:e.digest(r),value:r.text+' '}];
const rows=[{scenario:'single_run_text',oldChars:bytes(old(changed)),newChars:bytes(newer)}];
changed=structuredClone(p.runs);changed.find(x=>x.id===r.id).bold=!r.bold;rows.push({scenario:'run_format',oldChars:bytes(old(changed)),newChars:bytes([{op:'run-format',id:p.id,runId:r.id,expected:e.digest(r),value:{bold:!r.bold}}])});
changed=structuredClone(p.runs);changed.find(x=>x.id===r.id).text+=' ';changed.find(x=>x.id===r2.id).text+=' ';rows.push({scenario:'two_run_text_edits',oldChars:bytes(old(changed)),newChars:bytes([newer[0],{op:'run-text',id:p.id,runId:r2.id,expected:e.digest(r2),value:r2.text+' '}])});
const s=e.sourceUnits('أول.\n\nثان.\n\nثالث.\n\nرابع.\n\nخامس.');const fixture=e.prepare({title:'دَرْسٌ',paragraphs:[{type:'heading2',text:'عُنْوَانٌ'},...s.units.map(u=>({type:'paragraph',text:'نَصٌّ.',level:0,sourceIds:[u.id]}))]},s);const after=e.sourceUnits(s.raw.replace('أول','تعديل'),s),edited=structuredClone(fixture);edited.paragraphs[1].sourceIds=[after.units[0].id];edited.sourceHash=after.hash;const beforeHashes=e.fingerprints(fixture,s),afterHashes=e.fingerprints(edited,after);const invalid=fixture.paragraphs.filter(p=>beforeHashes[p.id]!==afterHashes[p.id]).map(p=>p.id);
const report={measurement:'JSON character counts, not model tokens or money',paragraphId:p.id,rows:rows.map(x=>({...x,reductionPercent:Math.round(1000*(1-x.newChars/x.oldChars))/10,transactionsBefore:1,transactionsAfter:1})),sourceChange:{fixtureParagraphs:fixture.paragraphs.length,oldGlobalInvalidations:fixture.paragraphs.length,newInvalidations:invalid.length,invalidIds:invalid,coherenceReviewRequired:true},limits:'Input payloads only; source-change case is synthetic. No live model token usage or economic estimate.'};
fs.writeFileSync(process.argv[3],JSON.stringify(report,null,2));console.log(JSON.stringify(report));
