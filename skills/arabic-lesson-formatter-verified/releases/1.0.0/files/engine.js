'use strict';
const crypto=require('crypto');
const clone=x=>structuredClone(x);
const stable=x=>Array.isArray(x)?x.map(stable):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,stable(x[k])])):x;
const digest=x=>crypto.createHash('sha256').update(JSON.stringify(stable(x))).digest('hex');
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
const text=p=>p.text??(p.runs||[]).map(r=>r.text).join('');
function objects(d){return d.paragraphs.flatMap((p,i)=>[{obj:p,kind:'paragraph',at:`paragraphs[${i}]`},...(p.runs||[]).map((r,j)=>({obj:r,kind:'run',at:`${p.id||i}.runs[${j}]`})),...(p.notes||[]).map((r,j)=>({obj:r,kind:'note',at:`${p.id||i}.notes[${j}]`}))]);}
function prepare(input,source){
 const d=clone(input);if(!Array.isArray(d.paragraphs)||d.paragraphs.some(p=>!p||typeof p!=='object'))throw Error('paragraphs: objects required');
 for(const p of d.paragraphs){for(const k of ['runs','notes'])if(p[k]!=null&&(!Array.isArray(p[k])||p[k].some(r=>!r||typeof r!=='object')))throw Error(`${k}: objects required`);
 if(p.text!=null&&p.runs){if(p.text!==p.runs.map(r=>r.text).join(''))throw Error(`${p.id}: text/runs mismatch`);delete p.text;}}
 const registry=d.ids||{next:{paragraph:1,run:1,note:1},issued:[],retired:[]};registry.next??={};registry.issued??=[];registry.retired??=[];
 const items=objects(d),seen=new Map(),issued=new Set(registry.issued),retired=new Set(registry.retired);
 for(const {obj,at} of items)if(obj.id!=null){if(typeof obj.id!=='string'||!obj.id.length)throw Error(`${at}: invalid id`);if(seen.has(obj.id))throw Error(`duplicate id ${obj.id}: ${seen.get(obj.id)} and ${at}`);if(retired.has(obj.id))throw Error(`retired id ${obj.id}`);seen.set(obj.id,at);issued.add(obj.id);}
 const prefixes={paragraph:'p',run:'r',note:'n'};
 for(const [kind,prefix] of Object.entries(prefixes)){let next=registry.next[kind]||1;if(!Number.isSafeInteger(next)||next<1)throw Error('invalid id counter');for(const id of issued){const m=id.match(new RegExp('^'+prefix+'(\\d+)$'));if(m)next=Math.max(next,Number(m[1])+1);}registry.next[kind]=next;}
 for(const {obj,kind} of items)if(!obj.id){let id;do{id=prefixes[kind]+registry.next[kind]++;}while(issued.has(id)||seen.has(id));obj.id=id;issued.add(id);seen.set(id,true);}
 for(const id of registry.issued)if(!seen.has(id))retired.add(id);
 registry.issued=[...issued];registry.retired=[...retired];d.ids=registry;d.version=4;d.sourceHash=source.hash;return d;
}
function sourceUnits(raw,previous){
 if(previous?.version===4&&previous.raw===raw&&previous.units.map(u=>u.text).join('')===raw)return clone(previous);
 const units=[];let start=0,buf='';for(const part of raw.match(/[^.!?؟\n]+[.!?؟\n]*|[.!?؟\n]+/gu)||[]){buf+=part;if(buf.length>=800||/\n\s*\n$/.test(buf)){units.push({start,end:start+buf.length,text:buf});start+=buf.length;buf='';}}if(buf)units.push({start,end:raw.length,text:buf});
 const old=previous?.units||[],used=new Set(),issued=new Set(previous?.ids?.issued||old.map(u=>u.id));let next=previous?.ids?.next||1;for(const id of issued){const m=id.match(/^u(\d+)$/);if(m)next=Math.max(next,+m[1]+1);}
 const context=(arr,i)=>[arr[i-1]?.text??null,arr[i].text,arr[i+1]?.text??null];
 for(let i=0;i<units.length;i++){const u=units[i],candidates=old.map((o,j)=>({o,j})).filter(x=>x.o.text===u.text&&!used.has(x.o.id));const newCount=units.filter(x=>x.text===u.text).length;let match;
 if(candidates.length===1&&newCount===1)match=candidates[0];else{const matches=candidates.filter(x=>digest(context(old,x.j))===digest(context(units,i)));const newMatches=units.filter((_,j)=>digest(context(units,j))===digest(context(units,i))).length;if(matches.length===1&&newMatches===1)match=matches[0];}
 if(match){u.id=match.o.id;used.add(u.id);}else{do{u.id='u'+next++;}while(issued.has(u.id));issued.add(u.id);}}
 return {version:4,hash:hash(raw),raw,units,ids:{next,issued:[...issued]},previousHash:previous?.hash??null};
}
function semantic(d,s,i){const p=d.paragraphs[i];const unitMap=new Map(s.units.map(u=>[u.id,u.text]));const summarize=q=>({id:q.id,text:text(q),type:q.type,level:q.level,source:(q.sourceIds||[]).map(id=>[id,unitMap.get(id)??null]),dependsOn:q.dependsOn||[]});
 const headers=[];for(let j=0;j<=i;j++){const q=d.paragraphs[j];if(q.type==='heading1'){headers.length=0;headers.push(q);}else if(q.type==='heading2'){if(headers[0]?.type==='heading1')headers.splice(1);else headers.length=0;headers.push(q);}}
 const involved=new Set([p.id,...(p.dependsOn||[])]);for(const q of d.paragraphs)if(q.dependsOn?.includes(p.id))involved.add(q.id);
 return digest({version:4,title:d.title||[d.bookTitle,d.lessonTitle],section:headers.map(summarize),neighbors:d.paragraphs.slice(Math.max(0,i-1),i+2).map(summarize),related:d.paragraphs.filter(q=>involved.has(q.id)).map(summarize)});
}
const fingerprints=(d,s)=>Object.fromEntries(d.paragraphs.map((p,i)=>[p.id,semantic(d,s,i)]));
const coherence=(d,s)=>digest({version:4,paragraphs:fingerprints(d,s),order:d.paragraphs.map(p=>p.id),source:s.units,omissions:d.omissions||[]});
const noteHash=p=>digest({notes:p.notes||[],anchors:(p.notes||[]).map(n=>(n.runIds||[n.runId]).filter(Boolean).map(id=>(()=>{const r=p.runs?.find(r=>r.id===id);return r?{id:r.id,text:r.text}:null;})())) });
function patches(input,ops,source,validate){
 if(!Array.isArray(ops)||!ops.length)throw Error('patch array required');const original=clone(input),d=clone(input);const writes=[];const plans=[];
 const claim=(key)=>{for(const old of writes)if(key===old||key.startsWith(old+'/')||old.startsWith(key+'/'))throw Error(`conflicting operations: ${key} / ${old}`);writes.push(key);};
 for(const op of ops){const p=original.paragraphs.find(p=>p.id===op.id);if(!p)throw Error(`unknown original paragraph ${op.id}`);let target=p,key=p.id;
 if(op.runId){target=p.runs?.find(r=>r.id===op.runId);key+='/runs/'+op.runId;}if(op.noteId){target=p.notes?.find(n=>n.id===op.noteId);key+='/notes/'+op.noteId;}if(!target)throw Error('unknown original target');if(op.expected!==digest(target))throw Error(`stale patch ${key}`);
 if(['delete','replace','split-run'].includes(op.op)){claim(key);if(op.op==='split-run')for(const n of p.notes||[])if((n.runIds||[n.runId]).includes(op.runId)){claim(p.id+'/notes/'+n.id+'/runId');claim(p.id+'/notes/'+n.id+'/runIds');}}
 else if(op.op==='insert'){claim(p.id+'/insertAfter');if(op.value?.id)throw Error('insert ids are generated');}
 else if(op.op==='move'){if(!original.paragraphs.some(q=>q.id===op.afterId)||op.afterId===op.id)throw Error('invalid move anchor');claim(p.id+'/position');claim(op.afterId+'/insertAfter');}
 else if(op.op==='run-text')claim(key+'/text');
 else if(op.op==='run-format'){if(!op.value||Object.keys(op.value).some(k=>!['bold','color','shading'].includes(k)))throw Error('run-format fields');for(const k of Object.keys(op.value))claim(key+'/'+k);}
 else if(op.op==='add-note'){if(op.value?.id)throw Error('note ids are generated');claim(p.id+'/notes/add');}
 else if(op.op==='update-note'){if(!op.value||Object.keys(op.value).some(k=>!['text','runId','runIds'].includes(k)))throw Error('note fields');for(const k of Object.keys(op.value))claim(key+'/'+k);}
 else if(op.op==='delete-note')claim(key);
 else if(op.op==='source')claim(p.id+'/sourceIds');
 else if(op.op==='update'){if(!op.value||Object.keys(op.value).some(k=>!['text','runs','type','level','notes','sourceIds','dependsOn'].includes(k)))throw Error('update fields');for(const k of Object.keys(op.value))claim(p.id+'/'+k);}
 else throw Error('unknown operation '+op.op);
 if(['run-text','run-format','split-run'].includes(op.op)&&!op.runId)throw Error('runId required');if(['update-note','delete-note'].includes(op.op)&&!op.noteId)throw Error('noteId required');plans.push(op);
 }
 for(const op of plans){let i=d.paragraphs.findIndex(p=>p.id===op.id),p=d.paragraphs[i];const run=p.runs?.find(r=>r.id===op.runId),note=p.notes?.find(n=>n.id===op.noteId);
 if(op.op==='delete')d.paragraphs.splice(i,1);
 else if(op.op==='replace')d.paragraphs[i]={...clone(op.value),id:p.id};
 else if(op.op==='insert')d.paragraphs.splice(i+1,0,clone(op.value));
 else if(op.op==='move'){d.paragraphs.splice(i,1);d.paragraphs.splice(d.paragraphs.findIndex(q=>q.id===op.afterId)+1,0,p);}
 else if(op.op==='update')Object.assign(p,clone(op.value));
 else if(op.op==='run-text'){if(typeof op.value!=='string')throw Error('run text required');run.text=op.value;}
 else if(op.op==='run-format'){for(const [k,val] of Object.entries(op.value))if(val===null)delete run[k];else run[k]=val;}
 else if(op.op==='source')p.sourceIds=clone(op.value);
 else if(op.op==='add-note')(p.notes??=[]).push(clone(op.value));
 else if(op.op==='update-note')Object.assign(note,clone(op.value));
 else if(op.op==='delete-note')p.notes=p.notes.filter(n=>n.id!==op.noteId);
 else if(op.op==='split-run'){if(!Array.isArray(op.value)||op.value.length<2||op.value.some(r=>!r||typeof r.text!=='string'||!r.text||r.id)||op.value.map(r=>r.text).join('')!==run.text)throw Error('split must preserve text exactly; ids generated');const j=p.runs.indexOf(run);const pieces=op.value.map(r=>({...run,...r,id:undefined}));pieces[0].id=run.id;p.runs.splice(j,1,...pieces);const next=prepare(d,source);Object.assign(d,next);p=d.paragraphs.find(q=>q.id===op.id);const ids=p.runs.slice(j,j+pieces.length).map(r=>r.id);for(const n of p.notes||[]){const anchors=n.runIds||[n.runId];if(anchors.includes(op.runId)){n.runIds=anchors.flatMap(id=>id===op.runId?ids:[id]);delete n.runId;}}}
 }
 const result=prepare(d,source),r=validate(result,source);if(r.errors.length)throw Error(r.errors.join('\n'));return result;
}
module.exports={digest,hash,text,prepare,sourceUnits,fingerprints,semantic,coherence,noteHash,patches,objects};
