const fs = require('fs');
const path = require('path');

const inputDir = path.resolve(process.cwd(), 'lessons_input');
const outputDir = path.resolve(process.cwd(), 'lessons_output');

// Ensure directories exist
if (!fs.existsSync(inputDir)) {
  fs.mkdirSync(inputDir, { recursive: true });
}
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

// Find txt files
let files = [];
try {
  files = fs.readdirSync(inputDir).filter(file => file.endsWith('.txt'));
} catch (err) {
  console.error("Error reading input directory:", err.message);
  process.exit(1);
}

console.log(JSON.stringify({
  inputDir: inputDir,
  outputDir: outputDir,
  files: files
}, null, 2));
