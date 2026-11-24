import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const job=JSON.parse(await fs.readFile(process.argv[2],'utf8'));
const mode=process.argv[3]||'build';
const preview=mode==='preview';

async function render(wb,file,kind,students){
  const dir=path.join(job.work_dir,'previews',kind);
  await fs.mkdir(dir,{recursive:true});
  const results=[];
  const ranges=[{sheet:'الإحصائيات',range:`A1:${kind==='grouped'?'I':'G'}${7+students.length}`}];
  for(const s of students){
    const last=(kind==='grouped'?s.grouped_rows:s.rows).length+1;
    if(kind==='grouped'&&!s.unchanged)ranges.push({sheet:s.sheet_name,range:`B1:E${last}`});
    else for(let first=1;first<=last;first+=30)ranges.push({sheet:s.sheet_name,range:`A${first}:K${Math.min(last,first+29)}`});
  }
  for(const [index,entry] of ranges.entries()){
    const image=await wb.render({sheetName:entry.sheet,range:entry.range,scale:1.1,format:'png'});
    const target=path.join(dir,`${String(index).padStart(3,'0')}.png`);
    await fs.writeFile(target,new Uint8Array(await image.arrayBuffer()));
    results.push({...entry,path:target});
  }
  await fs.writeFile(path.join(job.work_dir,`preview-${kind}.json`),JSON.stringify({preview_complete:true,results},null,2));
}

async function build(kind){
  const grouped=kind==='grouped';
  const target=grouped?job.grouped_path:job.detailed_path;
  if(preview){
    const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(target));
    await render(wb,target,kind,job.students); return;
  }
  const wb=Workbook.create();
  const summary=wb.worksheets.add('الإحصائيات');
  for(const s of job.students) wb.worksheets.add(s.sheet_name);
  for(const s of job.students){
    const sheet=wb.worksheets.getItem(s.sheet_name);
    const rows=grouped?s.grouped_rows:s.rows;
    const last=rows.length+1;
    const compact=grouped&&!s.unchanged;
    sheet.getRange('A1:K1').values=[job.headers];
    sheet.getRange(`A2:K${last}`).values=rows;
    sheet.getRange(`A1:K${last}`).format={font:{name:'Arial',size:11,color:'#203044'},verticalAlignment:'center',rowHeight:24};
    sheet.getRange(`B2:G${last}`).setNumberFormat('#,##0');
    for(const [col,width] of Object.entries(job.column_widths)) sheet.getRange(`${col}1:${col}${last}`).format.columnWidth=width;
    sheet.getRange(`C2:C${last}`).format.wrapText=true;
    sheet.getRange(`C2:C${last}`).format.horizontalAlignment='right';
    sheet.getRange(`H2:K${last}`).format.horizontalAlignment='right';
    sheet.getRange('A1:K1').format={fill:'#E8EDF4',font:{name:'Arial',size:11,bold:true,color:'#263B53'},rowHeight:29,horizontalAlignment:'center',verticalAlignment:'center'};
    if(compact){
      sheet.getRange(`C1:C${last}`).format.columnWidth=112;
      sheet.getRange(`E1:E${last}`).format.columnWidth=16;
      sheet.getRange('E1').values=[['مجموع الأوزان']];
    }
    for(let i=0;i<rows.length;i++){
      const row=i+2;
      const color=compact?(i%2===0?'#EDF3F9':'#FFFFFF'):(s.events[i].category==='weak'?'#FFF2DE':'#EDF3F9');
      sheet.getRange(`C${row}:E${row}`).format.fill=color;
      if(compact){
        const height=Math.max(32,Math.ceil(String(rows[i][2]).length/90)*19+14);
        if(height>409)throw Error(`Excel cell text exceeds one row capacity: ${s.name}, group ${i+1}`);
        sheet.getRange(`A${row}:K${row}`).format.rowHeight=height;
      }
      else if(rows[i][6]===1||String(rows[i][2]).length>34) sheet.getRange(`A${row}:K${row}`).format.rowHeight=40;
    }
    sheet.freezePanes.freezeRows(1);
  }
  const end=6+job.students.length;
  const total=end+1;
  const finalCol=grouped?'I':'G';
  summary.showGridLines=false; summary.tabColor='#203A57';
  summary.getRange(`A1:${finalCol}${total}`).format={font:{name:'Arial',size:11,color:'#203044'},verticalAlignment:'center',rowHeight:25};
  for(const [col,width] of Object.entries({A:6,B:38,C:15,D:21,E:21,F:19,G:19,...(grouped?{H:22,I:18}:{})})) summary.getRange(`${col}1:${col}${total}`).format.columnWidth=width;
  summary.getRange('B2').values=[[grouped?'إحصائيات خطط التثبيت المجمعة':'إحصائيات خطط التثبيت']];
  summary.getRange('B2:C2').merge();
  summary.getRange('B2').format={font:{name:'Arial',size:15,bold:true,color:'#203A57'},rowHeight:32,horizontalAlignment:'right'};
  summary.getRange('B3').values=[['عدد الطلاب']];
  summary.getRange('C3').formulas=[[`=COUNTA(B7:B${end})`]];
  summary.getRange('B4').values=[[`الدفعة التراكمية: ${job.settings.cumulative_pages} صفحات جديدة`]];
  summary.getRange('D4').values=[['الضعيف: ضعف الوزن الأصلي']];
  summary.getRange('F4:G4').merge();
  summary.getRange('F4').values=[['المتوسط: وزن التراكمي = صفحاته']];
  summary.getRange('B4:G4').format={font:{name:'Arial',size:10,color:'#516173'},rowHeight:30,wrapText:true};
  summary.getRange('B5').values=[['المتوسط']]; summary.getRange('B5').format.fill='#EDF3F9';
  summary.getRange('D5').values=[['الضعيف']]; summary.getRange('D5').format.fill='#FFF2DE';
  summary.getRange(`A6:${finalCol}6`).values=[['م','اسم الطالب',grouped?'العناصر الأصلية':'عدد العناصر','أوزان المتوسط','أوزان الضعيف','مجموع الأوزان','الأوزان ÷ ٦',...(grouped?['الوزن اليومي (÷ ٨)','العناصر الناتجة']:[])]];
  summary.getRange(`A6:${finalCol}6`).format={fill:'#203A57',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:30,horizontalAlignment:'center',verticalAlignment:'center'};
  for(let i=0;i<job.students.length;i++){
    const s=job.students[i],r=i+7,last=(grouped?s.grouped_rows:s.rows).length+1,quoted=s.sheet_name.replaceAll("'","''");
    summary.getRange(`A${r}:B${r}`).values=[[i+1,s.name]];
    if(grouped) summary.getRange(`C${r}:E${r}`).values=[[s.rows.length,s.medium_weight,s.weak_weight]];
    else{
      summary.getRange(`C${r}`).formulas=[[`=COUNT('${quoted}'!B2:B${last})`]];
      for(const [cat,col] of [['medium','D'],['weak','E']]){
        const runs=[];
        for(let j=0;j<s.events.length;j++) if(s.events[j].category===cat){const n=j+2;if(runs.length&&runs.at(-1)[1]===n-1)runs.at(-1)[1]=n;else runs.push([n,n]);}
        if(runs.length)summary.getRange(`${col}${r}`).formulas=[[`=SUM(${runs.map(([a,b])=>`'${quoted}'!E${a}:E${b}`).join(',')})`]];
        else summary.getRange(`${col}${r}`).values=[[0]];
      }
    }
    summary.getRange(`F${r}`).formulas=[[`=SUM('${quoted}'!E2:E${last})`]];
    summary.getRange(`G${r}`).formulas=[[`=F${r}/6`]];
    if(grouped){summary.getRange(`H${r}`).formulas=[[`=F${r}/8`]];summary.getRange(`I${r}`).formulas=[[`=COUNT('${quoted}'!B2:B${last})`]];}
    if(i%2===1)summary.getRange(`A${r}:${finalCol}${r}`).format.fill='#F2F5F8';
  }
  summary.getRange(`B${total}`).values=[['المجموع']];
  for(const col of ['C','D','E','F','G',...(grouped?['H','I']:[])])summary.getRange(`${col}${total}`).formulas=[[`=SUM(${col}7:${col}${end})`]];
  summary.getRange(`A${total}:${finalCol}${total}`).format={fill:'#E1E9F0',font:{name:'Arial',size:11,bold:true,color:'#203A57'},rowHeight:30};
  summary.getRange(`A7:F${total}`).setNumberFormat('#,##0');summary.getRange(`G7:G${total}`).setNumberFormat('#,##0.00');
  if(grouped){summary.getRange(`H7:H${total}`).setNumberFormat('#,##0.000');summary.getRange(`I7:I${total}`).setNumberFormat('#,##0');}
  summary.getRange(`B2:B${total}`).format.horizontalAlignment='right';summary.getRange(`C7:${finalCol}${total}`).format.horizontalAlignment='right';summary.freezePanes.freezeRows(6);
  wb.recalculate();
  for(let i=0;i<job.students.length;i++){
    const s=job.students[i],r=i+7;
    const actual=summary.getRange(`C${r}:${finalCol}${r}`).values[0];
    const expected=[s.rows.length,s.medium_weight,s.weak_weight,s.total_weight,s.total_weight/6,...(grouped?[s.daily_weight,s.grouped_rows.length]:[])];
    if(actual.some((v,j)=>typeof v!=='number'||Math.abs(v-expected[j])>1e-8))throw Error(`Summary mismatch ${s.name}`);
  }
  const s=job.students[0],cell=wb.worksheets.getItem(s.sheet_name).getRange('E2'),original=cell.values[0][0];
  cell.values=[[original+8]];
  if(Math.abs(summary.getRange('F7').values[0][0]-s.total_weight-8)>1e-8)throw Error('Recalculation failed');
  if(grouped&&Math.abs(summary.getRange('H7').values[0][0]-s.daily_weight-1)>1e-8)throw Error('Daily recalculation failed');
  cell.values=[[original]];wb.recalculate();
  const inspect=await wb.inspect({kind:'table',range:`'الإحصائيات'!A${total-1}:${finalCol}${total}`,tableMaxRows:2,tableMaxCols:9,maxChars:3000});
  await fs.writeFile(path.join(job.work_dir,`inspect-${kind}.ndjson`),inspect.ndjson);
  const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},summary:'formula error scan'});
  await fs.writeFile(path.join(job.work_dir,`formula-errors-${kind}.ndjson`),errors.ndjson);
  await (await SpreadsheetFile.exportXlsx(wb)).save(target);
  await fs.writeFile(path.join(job.work_dir,`export-${kind}.json`),JSON.stringify({export_complete:true,target,recalculation_test:true}));
}
for(const kind of ['detailed','grouped'])await build(kind);
process.exit(0);
