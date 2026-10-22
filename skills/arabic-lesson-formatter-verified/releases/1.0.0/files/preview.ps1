param([string]$InputDoc,[string]$OutputPdf)
$ErrorActionPreference='Stop'
$word=New-Object -ComObject Word.Application
$word.Visible=$false
try {$doc=$word.Documents.Open($InputDoc,$false,$true);$doc.ExportAsFixedFormat($OutputPdf,17);$doc.Close(0)} finally {$word.Quit()}
