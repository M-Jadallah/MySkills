'use strict';
const fs=require('fs'),path=require('path'),cp=require('child_process');
const v=require('./verified'),e=require('./engine');const {digest,prepare}=e;
const now=()=>new Date().toISOString();
const load=(f,otherwise={})=>fs.existsSync(f)?v.read(f):otherwise;
const codehash=()=>digest(['engine.js','verified.js','renderer.js','cli.js','format.json'].map(f=>fs.readFileSync(path.join(__dirname,f),'utf8')));
function validate(d,s){
 const errors=[];if(!d||!Array.isArray(d.paragraphs)||d.paragraphs.some(p=>!p||typeof p!=='object'))return {errors:['paragraphs: objects required'],warnings:[]};
 if(d.version!==4)errors.push('version 4 required; migrate first');
 if(!s||!Array.isArray(s.units)||s.units.some(u=>!u||typeof u.id!=='string'||typeof u.text!=='string'))return {errors:['invalid source units'],warnings:[]};
 if(new Set(s.units.map(u=>u.id)).size!==s.units.length)errors.push('duplicate source ids');
 if(s.raw!=null&&(e.hash(s.raw)!==s.hash||s.units.map(u=>u.text).join('')!==s.raw))errors.push('source snapshot integrity mismatch');
 const seen=new Set(),pids=new Set(d.paragraphs.map(p=>p.id));
 for(const p of d.paragraphs){
  if(typeof p.text!=='string'&&!Array.isArray(p.runs))errors.push(`${p.id}: text or runs required`);
  if(p.runs!=null&&(!Array.isArray(p.runs)||p.runs.some(r=>!r||typeof r.text!=='string'||!r.text)))errors.push(`${p.id}: nonempty runs required`);
  if(p.notes!=null&&(!Array.isArray(p.notes)||p.notes.some(n=>!n||typeof n.text!=='string'||!n.text.trim())))errors.push(`${p.id}: notes text required`);
  for(const k of ['sourceIds','dependsOn'])if(p[k]!=null&&(!Array.isArray(p[k])||p[k].some(id=>typeof id!=='string')))errors.push(`${p.id}: ${k} string array required`);
  if(Array.isArray(p.dependsOn)&&p.dependsOn.some(id=>!pids.has(id)||id===p.id))errors.push(`${p.id}: invalid dependency`);
 }
 if(errors.length)return {errors,warnings:[]};
 for(const {obj,at} of e.objects(d)){if(typeof obj.id!=='string'||!obj.id||seen.has(obj.id))errors.push(`missing/duplicate id at ${at}: ${obj.id}`);seen.add(obj.id);}
 for(const p of d.paragraphs)for(const n of p.notes||[]){if(n.runId&&n.runIds)errors.push(`${n.id}: runId OR runIds`);const ids=n.runIds||(n.runId?[n.runId]:[]);if(!Array.isArray(ids)||new Set(ids).size!==ids.length){errors.push(`${n.id}: invalid anchors`);continue;}const indexes=ids.map(id=>p.runs?.findIndex(r=>r.id===id)??-1);if(indexes.some((x,i)=>x<0||(i&&x!==indexes[i-1]+1)))errors.push(`${n.id}: anchors must exist and be consecutive`);}
 if(d.omissions!=null&&(!Array.isArray(d.omissions)||d.omissions.some(o=>!o||!s.units.some(u=>u.id===o.sourceId)||typeof o.reason!=='string'||!o.reason.trim())))errors.push('invalid omission');
 if(errors.length)return {errors,warnings:[]};try{const r=v.check(d,s);return {errors:[...errors,...r.errors],warnings:r.warnings};}catch(err){return {errors:[err.message],warnings:[]};}
}
function warnings(d,s,decisions={}){
 const r=validate(d,s);const result=[];
 for(const w of r.warnings){const p=d.paragraphs.find(p=>p.id===w.id);const t=e.text(p);if(w.type==='tashkeel'){const words=new Set(w.words||[]);for(const m of t.matchAll(/[\u0621-\u065F]+/gu)){if(!words.has(m[0]))continue;const context=t.slice(Math.max(0,m.index-35),m.index+m[0].length+35);const item={paragraphId:p.id,type:w.type,word:m[0],offset:m.index,context};item.id='w'+digest([item,e.semantic(d,s,d.paragraphs.indexOf(p))]).slice(0,24);const decision=decisions[item.id];item.status=decision?.status==='commented'&&!p.notes?.some(n=>n.id===decision.noteId)?'needs_review':decision?.status||'needs_review';result.push(item);}}else{const item={paragraphId:p.id,type:w.type,context:t.slice(0,120)};item.id='w'+digest([item,e.semantic(d,s,d.paragraphs.indexOf(p))]).slice(0,24);if(!result.some(x=>x.id===item.id)){const decision=decisions[item.id];item.status=decision?.status==='commented'&&!p.notes?.some(n=>n.id===decision.noteId)?'needs_review':decision?.status||'needs_review';result.push(item);}}}return {...r,warnings:result};
}
function currentState(old,d,s){
 const hashes=e.fingerprints(d,s),state={...old,reviewVersion:4,reviews:{},noteReviews:{},history:[...(old.history||[])]};
 if(old.reviewVersion!==4){if(old.reviews||old.visual)state.history.push({kind:'legacy',reviews:old.reviews,visual:old.visual});state.coherence=null;state.visual=null;}
 for(const p of d.paragraphs){const before=old.reviewVersion===4?old.reviews?.[p.id]:null;if(before?.hash===hashes[p.id])state.reviews[p.id]=before;else if(before)state.history.push({kind:'invalidated',paragraphId:p.id,record:before});const n=old.reviewVersion===4?old.noteReviews?.[p.id]:null;if(n?.hash===e.noteHash(p))state.noteReviews[p.id]=n;}
 const coh=e.coherence(d,s);if(state.coherence?.hash!==coh)state.coherence=null;
 const full=digest([d,s,codehash()]);if(old.fingerprint!==full)state.visual=null;
 state.semanticHashes=hashes;return state;
}
function pending(state,d,s){const current=currentState(state,d,s);return {content:d.paragraphs.filter(p=>!current.reviews[p.id]?.content).map(p=>p.id),language:d.paragraphs.filter(p=>!current.reviews[p.id]?.language).map(p=>p.id),notes:d.paragraphs.filter(p=>p.notes?.length&&!current.noteReviews[p.id]).map(p=>p.id),coherence:!current.coherence,visual:!current.visual};}
function status(state,d,s){const p=pending(state,d,s);return !p.content.length&&!p.language.length&&!p.notes.length&&!p.coherence&&!p.visual?(state.comments?'complete_with_notes':'complete'):'generated_pending_reviews';}
async function build(lesson,source,out){
 lesson=path.resolve(lesson);source=path.resolve(source);out=path.resolve(out);const d=v.read(lesson),s=v.read(source),r=validate(d,s);if(r.errors.length)throw Error(r.errors.join('\n'));const stateFile=out+'.state.json',old=load(stateFile),fingerprint=digest([d,s,codehash()]);
 if(old.reviewVersion===4&&old.fingerprint===fingerprint&&fs.existsSync(old.output)&&old.outputHash===e.hash(fs.readFileSync(old.output)))return {...old,resumed:true};
 const result=await v.build(d,out,s);const next={...currentState(old,d,s),...result,fingerprint,outputHash:e.hash(fs.readFileSync(result.output)),lesson,source,visual:null};next.status=status(next,d,s);v.save(stateFile,next);return next;
}
function checkFile(lesson,source){const d=v.read(lesson),s=v.read(source),ledger=load(lesson+'.warnings.json',{decisions:{}});const report=warnings(d,s,ledger.decisions);ledger.observed??={};for(const w of report.warnings)ledger.observed[w.id]=w;v.save(lesson+'.warnings.json',ledger);v.save(lesson+'.check.json',report);return report;}
function inspect(d,s,selector,old={},offset=0,limit=6000){
 const report=[];const selected=selector==='changed'?new Set([...pending(old,d,s).content,...pending(old,d,s).language]):new Set(selector.split(','));
 const format=p=>({paragraph:p,expected:digest(p),targets:[...(p.runs||[]).map(r=>({runId:r.id,expected:digest(r)})),...(p.notes||[]).map(n=>({noteId:n.id,expected:digest(n)}))]});
 if(selector.startsWith('source:')){const ids=new Set(selector.slice(7).split(','));for(let i=0;i<s.units.length;i++)if(ids.has(s.units[i].id))report.push({source:s.units[i],previous:s.units[i-1]||null,next:s.units[i+1]||null});if(report.length!==ids.size)throw Error('unknown source selector');}
 else{for(const id of selected)if(!d.paragraphs.some(p=>p.id===id))throw Error('unknown paragraph '+id);for(let i=0;i<d.paragraphs.length;i++){const p=d.paragraphs[i];if(!selected.has(p.id))continue;let section=[];for(const q of d.paragraphs.slice(0,i+1)){if(q.type==='heading1')section=[q];else if(q.type==='heading2'){section=section.filter(q=>q.type==='heading1');section.push(q);}}report.push({...format(p),section:section.map(q=>({id:q.id,text:e.text(q)})),previous:d.paragraphs[i-1]||null,next:d.paragraphs[i+1]||null,related:d.paragraphs.filter(q=>p.dependsOn?.includes(q.id)||q.dependsOn?.includes(p.id)),sources:s.units.filter(u=>p.sourceIds?.includes(u.id))});}}
 const payload=JSON.stringify(report);if(!Number.isInteger(offset)||offset<0||!Number.isInteger(limit)||limit<100||limit>20000)throw Error('inspect offset>=0 and limit 100..20000');const end=Math.min(payload.length,offset+limit);return {encoding:'json-fragment',offset,totalChars:payload.length,payload:payload.slice(offset,end),nextOffset:end<payload.length?end:null};
}
async function main(){const [cmd,...a]=process.argv.slice(2);
 if(cmd==='init'){const raw=fs.readFileSync(a[0],'utf8');v.save(a[1],e.sourceUnits(raw,load(a[2]||a[1],null)));}
 else if(cmd==='prepare'||cmd==='migrate'){const result=prepare(v.read(a[0]),v.read(a[1]));v.save(a[2]||a[0],result);}
 else if(cmd==='check'){const r=checkFile(...a),open=r.warnings.filter(w=>w.status==='needs_review');console.log(JSON.stringify({errors:r.errors.slice(0,10),errorCount:r.errors.length,openWarnings:open.length,types:Object.fromEntries([...new Set(open.map(w=>w.type))].map(t=>[t,open.filter(w=>w.type===t).length])),examples:open.slice(0,5),report:a[0]+'.check.json'}));if(r.errors.length)process.exitCode=1;}
 else if(cmd==='inspect'){console.log(JSON.stringify(inspect(v.read(a[0]),v.read(a[1]),a[2],a[3]&&a[3]!=='-'?load(a[3]):{},Number(a[4]||0),Number(a[5]||6000))));}
 else if(cmd==='apply'){const result=e.patches(v.read(a[0]),v.read(a[1]),v.read(a[2]),validate);v.save(a[0],result);console.log('applied atomically');}
 else if(cmd==='build'){const r=await build(...a);console.log(JSON.stringify({output:r.output,resumed:!!r.resumed,comments:r.comments,status:r.status}));}
 else if(cmd==='batch'){const jobs=v.read(a[0]),results=[];for(const job of jobs){try{const r=await build(job.lesson,job.source,job.output);results.push({output:r.output,status:r.status,resumed:!!r.resumed});}catch(err){results.push({output:job.output,status:'technical_failure',error:err.message});}v.save(a[1],results);}console.log(JSON.stringify({total:results.length,failed:results.filter(r=>r.status==='technical_failure').length,report:a[1]}));if(results.some(r=>r.status==='technical_failure'))process.exitCode=1;}
 else if(cmd==='preview'){cp.execFileSync('powershell.exe',['-NoProfile','-File',path.join(__dirname,'preview.ps1'),'-InputDoc',path.resolve(a[0]),'-OutputPdf',path.resolve(a[1])],{stdio:'inherit'});}
 else if(cmd==='status'){const old=v.read(a[0]),d=v.read(old.lesson),s=v.read(old.source),p=pending(old,d,s);if(!fs.existsSync(old.output)||old.outputHash!==e.hash(fs.readFileSync(old.output)))p.visual=true;console.log(JSON.stringify({pending:p,status:p.visual?'generated_pending_reviews':status(old,d,s),output:old.output}));}
 else if(cmd==='review'){
  const old=v.read(a[0]),d=v.read(old.lesson),s=v.read(old.source);if(old.fingerprint!==digest([d,s,codehash()])||old.outputHash!==e.hash(fs.readFileSync(old.output)))throw Error('stale review: rebuild');if(!a[2]?.trim())throw Error('review evidence required');const state=currentState(old,d,s),kind=a[1],record={evidence:a[2],at:now()};
  if(kind==='visual')state.visual={...record,hash:old.outputHash};else if(kind==='coherence')state.coherence={...record,hash:e.coherence(d,s)};
  else if(['content','language','notes'].includes(kind)){if(!a[3])throw Error('select paragraph ids or --all explicitly');const ids=a[3]==='--all'?d.paragraphs.map(p=>p.id):a[3].split(',');for(const id of ids){const p=d.paragraphs.find(p=>p.id===id);if(!p)throw Error('unknown review id '+id);if(kind==='notes')state.noteReviews[id]={...record,hash:e.noteHash(p)};else{state.reviews[id]??={hash:state.semanticHashes[id]};state.reviews[id][kind]=record;}}}
  else throw Error('content | language | notes | coherence | visual');state.status=status(state,d,s);v.save(a[0],state);console.log(JSON.stringify({status:state.status,pending:pending(state,d,s)}));
 }
 else if(cmd==='warning'){
  const [lesson,source,id,decision,evidence,noteId]=a;const ledger=load(lesson+'.warnings.json',{decisions:{}}),d=v.read(lesson),s=v.read(source);const r=warnings(d,s,ledger.decisions);if(!['needs_review','correct_in_context','corrected','commented'].includes(decision)||!evidence?.trim())throw Error('decision and evidence required');let w=r.warnings.find(w=>w.id===id);if(w&&decision==='corrected')throw Error('warning still present: fix text or choose correct_in_context/commented');if(!w&&decision==='corrected')w=ledger.observed?.[id]||ledger.decisions?.[id]?.warning||load(lesson+'.check.json',{warnings:[]}).warnings.find(w=>w.id===id);if(!w)throw Error('unknown warning; inspect current report');if(decision==='commented'&&!d.paragraphs.find(p=>p.id===w.paragraphId)?.notes?.some(n=>n.id===noteId))throw Error('existing noteId required');ledger.decisions[id]={status:decision,evidence,at:now(),warning:w,noteId};v.save(lesson+'.warnings.json',ledger);console.log(decision);
 }
 else throw Error('init | prepare | migrate | inspect | check | apply | build | batch | preview | status | review | warning');
}
if(require.main===module)main().catch(err=>{console.error(err.message);process.exitCode=1});module.exports={main,validate,prepare,build,digest,inspect,warnings,currentState,pending,status,codehash};
