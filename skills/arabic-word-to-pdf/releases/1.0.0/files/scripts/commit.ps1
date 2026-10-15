param(
    [Parameter(Mandatory=$true)][string]$Folder,
    [string]$RunRoot,
    [string]$CombinedName = 'جميع الدروس مرتبة.pdf',
    [string]$CombinedWordName = 'جميع الدروس مرتبة.docx',
    [switch]$CheckOnly
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path -LiteralPath $Folder).Path.TrimEnd('\')
$active=$null
try { $active=[Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application') } catch {}
$open=@()
if ($active) {
    foreach ($doc in $active.Documents) {
        if ((Split-Path $doc.FullName -Parent) -eq $root -and [IO.Path]::GetExtension($doc.FullName) -in @('.docx','.docm','.doc')) {
            if (!$doc.Saved) { throw ('Target Word document has unsaved edits; save and close it: '+$doc.FullName) }
            $open += $doc.FullName
        }
    }
}
if ($CheckOnly) { exit 0 }
$backup=(Resolve-Path -LiteralPath $RunRoot).Path
if ((Split-Path $backup -Parent) -ne $root) { throw 'RunRoot must belong directly to the target folder' }
$manifest=Get-Content -LiteralPath (Join-Path $backup 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$manifest=@($manifest)
$wordStage=Join-Path $backup '.word-stage';$pdfStage=Join-Path $backup '.pdf-stage';$pdfOutput=Join-Path $root 'PDF'
$combinedWord=Join-Path $root $CombinedWordName
$stagedCombinedWord=Join-Path $wordStage $CombinedWordName
if ([IO.Path]::GetFileName($CombinedWordName) -ne $CombinedWordName -or [IO.Path]::GetExtension($CombinedWordName) -ne '.docx') { throw 'Unsafe combined Word filename' }
if (!(Test-Path -LiteralPath $stagedCombinedWord -PathType Leaf)) { throw 'Missing staged combined Word file' }
$oldCombinedWord=Join-Path $backup 'combined-word-before.docx'
$hadCombinedWord=Test-Path -LiteralPath $combinedWord -PathType Leaf
$generated=@($manifest.pdf)+@($CombinedName,'فهرس الدروس والصفحات.csv','verification.json')
function SharedHash($path) {
    $stream=[IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
    $sha=[Security.Cryptography.SHA256]::Create()
    try { return [Convert]::ToBase64String($sha.ComputeHash($stream)) } finally { $stream.Dispose();$sha.Dispose() }
}
foreach ($record in $manifest) {
    if ([IO.Path]::GetFileName($record.source) -ne $record.source) { throw 'Unsafe source name' }
    if ((SharedHash (Join-Path $root $record.source)) -ne $record.source_hash) { throw ('Source changed during work: '+$record.source) }
}
foreach ($name in $generated) {
    if ([IO.Path]::GetFileName($name) -ne $name) { throw 'Unsafe generated filename' }
    if (!(Test-Path -LiteralPath (Join-Path $pdfStage $name) -PathType Leaf)) { throw ('Missing staged output: '+$name) }
}
if ($hadCombinedWord) { Copy-Item -LiteralPath $combinedWord -Destination $oldCombinedWord -Force }
$oldPDF=Join-Path $backup 'pdf-before'
New-Item -ItemType Directory -Path $oldPDF,$pdfOutput -Force | Out-Null
foreach ($name in $generated) {
    $existing=Join-Path $pdfOutput $name
    if (Test-Path -LiteralPath $existing) { Copy-Item -LiteralPath $existing -Destination (Join-Path $oldPDF $name) }
}
foreach ($path in $open) {
    foreach ($doc in @($active.Documents)) { if ($doc.FullName -eq $path) { $doc.Close(0);break } }
}
try {
    foreach ($record in $manifest) { Copy-Item -LiteralPath (Join-Path $wordStage $record.source) -Destination (Join-Path $root $record.source) -Force }
    Copy-Item -LiteralPath $stagedCombinedWord -Destination $combinedWord -Force
    foreach ($name in $generated) { Copy-Item -LiteralPath (Join-Path $pdfStage $name) -Destination (Join-Path $pdfOutput $name) -Force }
    foreach ($record in $manifest) {
        if ((SharedHash (Join-Path $root $record.source)) -ne (SharedHash (Join-Path $wordStage $record.source))) { throw 'Final Word copy mismatch' }
    }
    if ((SharedHash $combinedWord) -ne (SharedHash $stagedCombinedWord)) { throw 'Final combined Word copy mismatch' }
    foreach ($name in $generated) {
        if ((SharedHash (Join-Path $pdfOutput $name)) -ne (SharedHash (Join-Path $pdfStage $name))) { throw 'Final PDF copy mismatch' }
    }
} catch {
    foreach ($record in $manifest) { Copy-Item -LiteralPath (Join-Path $backup $record.source) -Destination (Join-Path $root $record.source) -Force }
    if ($hadCombinedWord) { Copy-Item -LiteralPath $oldCombinedWord -Destination $combinedWord -Force } elseif (Test-Path -LiteralPath $combinedWord) { Remove-Item -LiteralPath $combinedWord }
    foreach ($name in $generated) {
        $old=Join-Path $oldPDF $name;$target=Join-Path $pdfOutput $name
        if (Test-Path -LiteralPath $old) { Copy-Item -LiteralPath $old -Destination $target -Force } elseif (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target }
    }
    throw
} finally {
    foreach ($path in $open) { [void]$active.Documents.Open($path) }
}
