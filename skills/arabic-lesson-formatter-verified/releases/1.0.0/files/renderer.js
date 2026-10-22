const F=require('./format.json');
const fs = require('fs');
const path = require('path');
const {Document,Packer,Paragraph,TextRun,AlignmentType,HeadingLevel,LevelFormat,ShadingType}=require('docx');
const JSZip=require('jszip');
const normalize=s=>s.replace(/\S+/gu,t=>/https?:\/\/|@/.test(t)||(/[A-Za-z]/.test(t)&&(!/[\u0621-\u064A]/.test(t)||/[A-LN-Za-ln-z]/.test(t)))?t:t.replace(/(?<=[\u0621-\u065F])[mM]|[mM](?=[\u0621-\u065F])/gu,'م').replace(/[0-9]/g,c=>'٠١٢٣٤٥٦٧٨٩'[+c]));
function validate(d){
 const errors=[]; const types=['heading1','heading2','paragraph','bullet','summary','closing'];
 if(!d||!Array.isArray(d.paragraphs)||!d.paragraphs.length)return ['paragraphs must be nonempty'];
 if(!d.paragraphs.some(p=>p&&p.type==='heading2'))errors.push('heading2 required');
 if(!d.title && !(d.bookTitle&&d.lessonTitle))errors.push('title or bookTitle and lessonTitle required');
 let inside=false,parent=false;
 const check=(s,label)=>{if(typeof s!=='string'||!s.trim()){errors.push(label+' requires text');return;} const words=normalize(s).match(/[\u0621-\u064A\u0671\u064B-\u065F\u0670]+/gu)||[];if(words.some(w=>(w.match(/[\u0621-\u064A\u0671]/g)||[]).length>1&&!/[\u064B-\u065F\u0670]/.test(w)))void 0;};
 for(const k of ['title','bookTitle','lessonTitle'])if(d[k]!=null)check(d[k],k);
 d.paragraphs.forEach((p,i)=>{
  if(!p||!types.includes(p.type)){errors.push('invalid type '+i);return;}
  check(p.text,'paragraph '+i);
  if(p.type==='heading1'||p.type==='heading2'||p.type==='closing'){inside=p.type!=='closing';parent=false;if(p.level!=null)errors.push('heading/closing cannot have level '+i);}
  else {if(inside||p.type==='bullet'){if(![0,1].includes(p.level))errors.push('list level required '+i);}else if(p.level!=null&&![0,1].includes(p.level))errors.push('invalid level '+i);
   if(p.level===1&&!parent)errors.push('orphan child '+i); if(p.level===0)parent=true;
   if(p.level!=null&&/^\s*[-•]/.test(p.text||''))errors.push('do not embed list marker '+i);
  }
  if(p.runs&&p.runs.some(r=>!r||typeof r.text!=='string')){errors.push('invalid run '+i);return;}if(p.runs!=null){if(!Array.isArray(p.runs)||!p.runs.length){errors.push('invalid runs '+i);return;}if(p.runs.map(r=>r.text).join('')!==p.text)errors.push('runs/text mismatch '+i);for(const r of p.runs){if(typeof r.text!=='string'||(r.bold!=null&&typeof r.bold!=='boolean')||(r.color!=null&&r.color!==F.important)||(r.shading!=null&&r.shading!==F.constraintFill))errors.push('invalid run '+i);}}
 });return errors;
}
function runs(p,color=F.body,bold=false){
 let stack=[]; const pairs={'[':']','(':')','«':'»'};const result=[];
 const full=normalize((p.runs||[{text:p.text}]).map(r=>r.text).join(''));const spans=[];let opens=[];for(let i=0;i<full.length;i++){if(pairs[full[i]])opens.push([i,pairs[full[i]]]);else if(')]»'.includes(full[i])){const q=opens.pop();if(q&&q[1]===full[i])spans.push([q[0],i]);}}let position=0;for(const r of p.runs||[{text:p.text}]){
  let buf='',last;
  const flush=()=>{if(buf)result.push(new TextRun({text:buf,font:{name:F.font,cs:F.font},size:F.size,sizeComplexScript:F.size,bold:bold||r.bold,boldComplexScript:bold||r.bold,color:last,rightToLeft:true,...(r.shading?{shading:{type:ShadingType.CLEAR,fill:r.shading}}:{})}));buf='';};
  for(const c of normalize(r.text)){let brown=spans.some(([a,b])=>position>=a&&position<=b);position+=c.length;const col=brown?F.quote:p.type?.startsWith('heading')?color:r.color||color;if(col!==last){flush();last=col;}buf+=c;if(pairs[c])stack.push(pairs[c]);else if(stack.at(-1)===c)stack.pop();}flush();
 }return result;
}
async function generate(d,out){
 const errors=validate(d);if(errors.length)throw Error(errors.join('\n'));
 const base={bidirectional:true,alignment:AlignmentType.START,spacing:{before:0,after:0,line:240,lineRule:'auto'}};
 const heading=(p,level,fill,color)=>new Paragraph({...base,heading:level,keepNext:true,spacing:{...base.spacing,before:level===HeadingLevel.HEADING_1?180:0},shading:{type:ShadingType.CLEAR,fill},children:runs(p,color,true)});
 const children=[heading({text:d.title||`${d.bookTitle} / ${d.lessonTitle}`},HeadingLevel.HEADING_1,F.titleFill,F.title)];
 for(const p of d.paragraphs){if(p.type==='heading1'||p.type==='heading2')children.push(heading(p,p.type==='heading1'?HeadingLevel.HEADING_1:HeadingLevel.HEADING_2,p.type==='heading1'?F.h1Fill:F.h2Fill,p.type==='heading1'?F.title:F.body));else children.push(new Paragraph({...base,...(p.level!=null?{numbering:{reference:'hierarchy',level:p.level},indent:{right:p.level===0?360:720,hanging:240}}:p.type==='paragraph'?{indent:{firstLine:283}}:{}),...(p.type==='closing'?{spacing:{...base.spacing,before:120}}:{}),children:runs(p,F.body,['summary','closing'].includes(p.type))}));}
 const doc=new Document({styles:{default:{document:{run:{font:F.font,size:F.size,sizeComplexScript:F.size}}}},numbering:{config:[{reference:'hierarchy',levels:[0,1].map(level=>({level,format:LevelFormat.BULLET,text:level===0?'-':'•',alignment:AlignmentType.START,style:{paragraph:{indent:{right:level===0?360:720,hanging:240}},run:{font:F.font,size:F.size,color:F.title}}}))}]},sections:[{properties:{page:{size:{width:12240,height:15840},margin:{top:F.margin,bottom:F.margin,right:F.margin,left:F.margin}}},children}]});
 let buffer=await Packer.toBuffer(doc);const zip=await JSZip.loadAsync(buffer);const rel='word/_rels/document.xml.rels';let xml=await zip.file(rel).async('string');if(zip.file('word/fontTable.xml')&&!xml.includes('/relationships/fontTable'))zip.file(rel,xml.replace('</Relationships>','<Relationship Id="rIdFontTable" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" Target="fontTable.xml"/></Relationships>'));
 for(const part of ['word/document.xml','word/numbering.xml']){zip.file(part,(await zip.file(part).async('string')).replace(/(<w:ind\b[^>]*?)w:right=/g,'$1w:start='));}
 fs.mkdirSync(path.dirname(path.resolve(out)),{recursive:true});fs.writeFileSync(out,await zip.generateAsync({type:'nodebuffer',compression:'DEFLATE'}));
}
if(require.main===module){const a=process.argv.slice(2),input=a[a.indexOf('--input')+1],output=a[a.indexOf('--output')+1];if(!a.includes('--input')||!a.includes('--output')||!input||!output){console.error('node formatter.js --input lesson.json --output lesson.docx');process.exitCode=1;}else{try{const d=JSON.parse(fs.readFileSync(input,'utf8').replace(/^\uFEFF/,''));generate(d,output).then(()=>console.log('Generated; pending visual/content review: '+output)).catch(e=>{console.error(e.message);process.exitCode=1;});}catch(e){console.error(e.message);process.exitCode=1;}}}
module.exports={validate,generate,normalize};



