const fs = require('fs');
const path = require('path');
const { Document, Packer, Paragraph, TextRun, AlignmentType, HeadingLevel } = require('docx');

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

// Function to split text into runs with brown color inside brackets
function createTextRuns(text, defaultColor, isBold = false) {
  if (!text) return [];
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

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPath, buffer);
  console.log(`Successfully generated formatted document at: ${outputPath}`);
}).catch(err => {
  console.error("Error generating document buffer:", err.message);
  process.exit(1);
});
