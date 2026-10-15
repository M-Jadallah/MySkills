const fs = require('fs');
const path = require('path');
const { Document, Packer, Paragraph, TextRun, AlignmentType, HeadingLevel } = require('docx');
const JSZip = require('jszip');

// Argument parser
const args = process.argv.slice(2);
let inputPath = '';
let outputPath = '';
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--input' && args[i + 1]) {
    inputPath = args[i + 1];
  } else if (args[i] === '--output' && args[i + 1]) {
    outputPath = args[i + 1];
  }
}

if (!inputPath || !outputPath) {
  console.error("Usage: node formatter.js --input <input.json> --output <output.docx>");
  process.exit(1);
}

// Function to split text into runs with brown color inside brackets and clean m/M
function createTextRuns(text, defaultColor, isBold = false) {
  if (!text) return [];
  
  // Clean text by replacing English 'm' and 'M' with Arabic 'م'
  text = text.replace(/[mM]/g, 'م');
  
  // Match brackets: [] (square), () (parentheses), «» (quotation/gillemets)
  const regex = /(\[[^\]]*\]|\([^)]*\)|«[^»]*»)/g;
  const parts = text.split(regex);
  return parts.filter(p => p !== "").map(part => {
    const isBrown = part.startsWith('[') || part.startsWith('(') || part.startsWith('«');
    return new TextRun({
      text: part,
      font: { name: "Traditional Arabic" },
      size: 44,
      bold: isBold,
      color: isBrown ? "8B4513" : defaultColor,
      rightToLeft: true,
    });
  });
}

// Read and parse input JSON
let data;
try {
  let fileContent = fs.readFileSync(inputPath, 'utf8');
  if (fileContent.charCodeAt(0) === 0xFEFF) {
    fileContent = fileContent.slice(1);
  }
  data = JSON.parse(fileContent);
} catch (err) {
  console.error("Error reading/parsing input JSON:", err.message);
  process.exit(1);
}

// Reject structurally incomplete lessons and plainly unvocalized Arabic words.
// This is a minimum mechanical check; full and contextually correct tashkeel
// still requires review before the document is accepted.
function validateLesson(data) {
  const errors = [];
  const allowedTypes = new Set(['heading1', 'heading2', 'summary', 'bullet', 'closing', 'paragraph']);
  if (!data || !Array.isArray(data.paragraphs) || data.paragraphs.length === 0) {
    return ['paragraphs must be a non-empty array'];
  }
  if (!data.paragraphs.some(p => p && p.type === 'heading2' && typeof p.text === 'string' && p.text.trim())) {
    errors.push('at least one non-empty heading2 is required');
  }

  const fields = [
    ['bookTitle', data.bookTitle],
    ['lessonTitle', data.lessonTitle],
    ...data.paragraphs.map((p, i) => [`paragraphs[${i}]`, p && p.text]),
  ];
  for (const [name, value] of fields) {
    if (value === undefined || value === null || value === '') continue;
    if (typeof value !== 'string') {
      errors.push(`${name} must be text`);
      continue;
    }
    const words = value.match(/[\u0621-\u064A\u0671-\u06D3\u064B-\u065F\u0670\u06D6-\u06ED]+/gu) || [];
    const unvocalized = words.filter(word => {
      const letters = word.match(/[\u0621-\u064A\u0671-\u06D3]/gu) || [];
      return letters.length >= 2 && !/[\u064B-\u065F\u0670\u06D6-\u06ED]/u.test(word);
    });
    if (unvocalized.length) {
      errors.push(`${name} contains unvocalized words: ${unvocalized.slice(0, 5).join(', ')}`);
    }
  }
  data.paragraphs.forEach((p, i) => {
    if (!p || !allowedTypes.has(p.type)) errors.push(`paragraphs[${i}] has an invalid type`);
    if (!p || typeof p.text !== 'string' || !p.text.trim()) errors.push(`paragraphs[${i}] has no text`);
  });
  return errors;
}

const validationErrors = validateLesson(data);
if (validationErrors.length) {
  console.error('Lesson validation failed:\n' + validationErrors.map(e => `- ${e}`).join('\n'));
  process.exit(1);
}

const children = [];

// 1. Book Title (bold, #1F1F1F)
if (data.bookTitle) {
  children.push(new Paragraph({
    bidirectional: true,
    alignment: AlignmentType.RIGHT,
    spacing: { before: 0, after: 0, line: 240, lineRule: "auto" },
    children: createTextRuns(data.bookTitle, "1F1F1F", true)
  }));
}

// 2. Lesson Title (bold, #1F1F1F, brackets brown)
if (data.lessonTitle) {
  children.push(new Paragraph({
    bidirectional: true,
    alignment: AlignmentType.RIGHT,
    spacing: { before: 0, after: 0, line: 240, lineRule: "auto" },
    children: createTextRuns(data.lessonTitle, "1F1F1F", true)
  }));
}

// 3. Process paragraphs
if (data.paragraphs && Array.isArray(data.paragraphs)) {
  data.paragraphs.forEach((p, idx) => {
    const type = p.type || 'paragraph';
    const text = p.text || '';
    
    if (type === 'heading1') {
      const isFirst = (idx === 0);
      children.push(new Paragraph({
        heading: HeadingLevel.HEADING_1,
        bidirectional: true,
        alignment: AlignmentType.RIGHT,
        spacing: {
          before: isFirst ? 0 : 180,
          after: 0,
          line: 240,
          lineRule: "auto"
        },
        keepNext: true,
        children: createTextRuns(text, "C00000", true)
      }));
    } else if (type === 'heading2') {
      children.push(new Paragraph({
        heading: HeadingLevel.HEADING_2,
        bidirectional: true,
        alignment: AlignmentType.RIGHT,
        spacing: { before: 0, after: 0, line: 240, lineRule: "auto" },
        children: createTextRuns(text, "1F1F1F", true)
      }));
    } else if (type === 'summary') {
      children.push(new Paragraph({
        bidirectional: true,
        alignment: AlignmentType.RIGHT,
        spacing: { before: 0, after: 0, line: 240, lineRule: "auto" },
        children: createTextRuns(text, "1F1F1F", true)
      }));
    } else if (type === 'bullet') {
      children.push(new Paragraph({
        bidirectional: true,
        alignment: AlignmentType.RIGHT,
        indent: { right: 259 },
        spacing: { before: 0, after: 0, line: 240, lineRule: "auto" },
        children: createTextRuns(text, "1F1F1F", false)
      }));
    } else if (type === 'closing') {
      children.push(new Paragraph({
        bidirectional: true,
        alignment: AlignmentType.RIGHT,
        spacing: { before: 120, after: 0, line: 240, lineRule: "auto" },
        children: createTextRuns(text, "1F1F1F", true)
      }));
    } else {
      children.push(new Paragraph({
        bidirectional: true,
        alignment: AlignmentType.RIGHT,
        spacing: { before: 0, after: 0, line: 240, lineRule: "auto" },
        children: createTextRuns(text, "1F1F1F", false)
      }));
    }
  });
}

// Build Document
const doc = new Document({
  styles: {
    default: {
      document: {
        run: {
          font: "Traditional Arabic",
          size: 44,
          color: "1F1F1F"
        }
      }
    }
  },
  sections: [{
    properties: {
      page: {
        size: {
          width: 12240,
          height: 15840
        },
        margin: {
          top: 720,
          right: 720,
          bottom: 720,
          left: 720
        }
      },
      bidi: true
    },
    children: children
  }]
});

Packer.toBuffer(doc).then(async buffer => {
  // Some docx versions emit fontTable.xml without registering it in the
  // document relationships, which makes strict validators reject the file.
  const zip = await JSZip.loadAsync(buffer);
  const relationshipsPath = 'word/_rels/document.xml.rels';
  const relationshipsFile = zip.file(relationshipsPath);
  if (zip.file('word/fontTable.xml') && relationshipsFile) {
    let relationships = await relationshipsFile.async('string');
    if (!relationships.includes('/relationships/fontTable')) {
      const fontTableRelationship = '<Relationship Id="rIdFontTable" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" Target="fontTable.xml"/>';
      relationships = relationships.replace('</Relationships>', `${fontTableRelationship}</Relationships>`);
      zip.file(relationshipsPath, relationships);
      buffer = await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' });
    }
  }

  fs.writeFileSync(outputPath, buffer);
  console.log(`Successfully generated formatted document at: ${outputPath}`);
}).catch(err => {
  console.error("Error generating document buffer:", err.message);
  process.exit(1);
});
