param(
    [Parameter(Mandatory=$true)][string]$Folder,
    [Parameter(Mandatory=$true)][string]$PythonPath,
    [string]$CombinedName = 'جميع الدروس مرتبة.pdf',
    [string]$CombinedWordName = 'جميع الدروس مرتبة.docx',
    [double]$FirstLineIndentCm = 0.5,
    [double]$FrameInset = 8,
    [double]$FooterY = 25,
    [double]$FooterSize = 11
)
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'Run this script with PowerShell 7 (pwsh), not Windows PowerShell 5.1' }
$root = (Resolve-Path -LiteralPath $Folder).Path.TrimEnd('\')
if (!(Test-Path -LiteralPath $root -PathType Container)) { throw 'Folder not found' }
if ([IO.Path]::GetFileName($CombinedName) -ne $CombinedName -or [IO.Path]::GetExtension($CombinedName) -ne '.pdf') { throw 'CombinedName must be a PDF filename without a directory' }
if ([IO.Path]::GetFileName($CombinedWordName) -ne $CombinedWordName -or [IO.Path]::GetExtension($CombinedWordName) -ne '.docx') { throw 'CombinedWordName must be a DOCX filename without a directory' }
if (!(Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw 'Python executable not found' }
if ($FirstLineIndentCm -lt 0 -or $FirstLineIndentCm -gt 2.5) { throw 'FirstLineIndentCm must be between 0 and 2.5 cm' }
$firstLineIndentPt = 72.0 * $FirstLineIndentCm / 2.54
$files = @(Get-ChildItem -LiteralPath $root -File | Where-Object { $_.Extension.ToLowerInvariant() -in @('.docx','.docm','.doc') -and !$_.Name.StartsWith('~$') -and $_.Name -ne $CombinedWordName })
if (!$files.Count) { throw 'No Word documents directly in the supplied folder' }
$records = @(); $seen = @{}; $pdfNames = @{}
foreach ($file in $files) {
    $match = [regex]::Match($file.BaseName,'^\s*([0-9٠-٩۰-۹]+)')
    if (!$match.Success) { throw ('Missing lesson number in filename: '+$file.Name) }
    $digits = ''; foreach ($char in $match.Groups[1].Value.ToCharArray()) { $digits += [Globalization.CharUnicodeInfo]::GetDecimalDigitValue($char).ToString() }
    $number = [long]$digits
    if ($seen.ContainsKey($number)) { throw ('Duplicate lesson number: '+$number) }; $seen[$number] = $true
    $pdfName = $file.BaseName + '.pdf'
    if ($pdfNames.ContainsKey($pdfName) -or $pdfName -eq $CombinedName) { throw ('PDF filename collision: '+$pdfName) }; $pdfNames[$pdfName]=$true
    $records += [pscustomobject]@{Number=$number;Name=$file.Name;Path=$file.FullName;PDF=$pdfName}
}
$records = @($records | Sort-Object Number)
$runId = (Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+([guid]::NewGuid().ToString('N').Substring(0,6))
$backup = Join-Path $root ('نسخ احتياطية Word وPDF - '+$runId)
$wordStage = Join-Path $backup '.word-stage'
$pdfStage = Join-Path $backup '.pdf-stage'
$pdfOutput = Join-Path $root 'PDF'
function SharedHash([string]$path) {
    $stream = [IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [Convert]::ToBase64String($sha.ComputeHash($stream)) } finally { $stream.Dispose();$sha.Dispose() }
}
function Stories($doc) {
    foreach ($first in $doc.StoryRanges) {
        $story=$first; $index=0
        while ($null -ne $story) {
            $index++
            [pscustomobject]@{Key=([string]$story.StoryType+'/'+$index);Range=$story}
            $story=$story.NextStoryRange
        }
    }
}
function Meaningful($paragraph) { return (($paragraph.Range.Text -replace '[\s\x07]','').Length -gt 0) }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'commit.ps1') -Folder $root -CheckOnly
if ($LASTEXITCODE -ne 0) { throw 'Open target document check failed; originals untouched' }
New-Item -ItemType Directory -Path $backup,$wordStage,$pdfStage -Force | Out-Null
foreach ($record in $records) {
    $record | Add-Member -NotePropertyName Hash -NotePropertyValue (SharedHash $record.Path)
    Copy-Item -LiteralPath $record.Path -Destination (Join-Path $backup $record.Name)
    Copy-Item -LiteralPath $record.Path -Destination (Join-Path $wordStage $record.Name)
}
$app = New-Object -ComObject Word.Application
$app.Visible=$false; $app.DisplayAlerts=0; $app.AutomationSecurity=3
$manifest=@();$done=0
try {
    foreach ($record in $records) {
        $staged=Join-Path $wordStage $record.Name
        $doc=$app.Documents.Open($staged,$false,$false)
        $expected=@{}; $centered=0; $changed=0; $indented=0
        try {
            foreach ($item in Stories $doc) {
                $range=$item.Range; $before=$range.Text; $mask=@()
                foreach ($p in $range.Paragraphs) {
                    $isCenter=($p.Format.Alignment -eq 1)
                    if (!(Meaningful $p)) {
                        $mask += [pscustomobject]@{Center=[bool]$isCenter;FirstLineIndent=[double]$p.Format.FirstLineIndent}
                        continue
                    }
                    if ($isCenter) { $centered++ }
                    $format=$p.Format
                    $format.ReadingOrder=0
                    if ($isCenter) { $format.Alignment=1 } else { $format.Alignment=2 }
                    if ($item.Range.StoryType -eq 1 -and !$isCenter -and $format.OutlineLevel -eq 10 -and !$p.Range.Information(12) -and $p.Range.ListFormat.ListType -eq 0 -and [Math]::Abs([double]$format.FirstLineIndent) -le 0.2 -and $FirstLineIndentCm -gt 0) {
                        $format.FirstLineIndent=$firstLineIndentPt
                        $indented++
                    }
                    $mask += [pscustomobject]@{Center=[bool]$isCenter;FirstLineIndent=[double]$format.FirstLineIndent}
                    $changed++
                }
                if ($range.Text -cne $before) { throw ('Text changed: '+$record.Name+' / '+$item.Key) }
                $expected[$item.Key]=[pscustomobject]@{Text=$before;Mask=$mask}
            }
            $doc.Save()
            Write-Output ('Staged Word saved: '+$record.Name)
        } finally { $doc.Close(0) }
        $doc=$app.Documents.Open($staged,$false,$true)
        Write-Output ('Reopened for verification: '+$record.Name)
        try {
            $checkedStories=0
            foreach ($item in Stories $doc) {
                $checkedStories++
                $old=$expected[$item.Key]
                if ($null -eq $old -or $item.Range.Text -cne $old.Text -or $item.Range.Paragraphs.Count -ne $old.Mask.Count) { throw ('Text or paragraph structure changed after saving: '+$record.Name) }
                $index=0
                foreach ($p in $item.Range.Paragraphs) {
                    $wanted=$old.Mask[$index];$index++
                    if (!(Meaningful $p)) { continue }
                    $want=2; if ($wanted.Center) { $want=1 }
                    if ($p.Format.Alignment -ne $want -or $p.Format.ReadingOrder -ne 0) { throw ('Word alignment/center verification failed: '+$record.Name) }
                    if ([Math]::Abs([double]$p.Format.FirstLineIndent - $wanted.FirstLineIndent) -gt 0.2) { throw ('Word first-line indentation verification failed: '+$record.Name) }
                }
            }
            if ($checkedStories -ne $expected.Count) { throw 'A Word story disappeared' }
            $doc.Repaginate()
            Write-Output ('Word text and alignment verified: '+$record.Name)
            $pages=$doc.ComputeStatistics(2)
            $doc.ExportAsFixedFormat((Join-Path $pdfStage $record.PDF),17)
        } finally { $doc.Close(0) }
        $manifest += [pscustomobject]@{number=$record.Number;source=$record.Name;source_hash=$record.Hash;pdf=$record.PDF;word_pages=$pages;centered_preserved=$centered;first_line_indented=$indented;paragraphs_checked=$changed}
        $done++; Write-Output ('Word and PDF verified: '+$done+'/'+$records.Count)
    }
} finally { $app.Quit() }
$manifestPath=Join-Path $backup 'manifest.json'
ConvertTo-Json -InputObject @($manifest) -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
& (Join-Path $PSScriptRoot 'merge_word.ps1') -RunRoot $backup -PythonPath $PythonPath -CombinedWordName $CombinedWordName
if (!(Test-Path -LiteralPath (Join-Path $wordStage $CombinedWordName) -PathType Leaf)) { throw ('Word merge failed; originals untouched. Staging: '+$backup) }
& $PythonPath (Join-Path $PSScriptRoot 'pdf_pipeline.py') --manifest $manifestPath --pdf-dir $pdfStage --combined-name $CombinedName --frame-inset $FrameInset --footer-y $FooterY --footer-size $FooterSize
if ($LASTEXITCODE -ne 0) { throw ('PDF validation failed; originals untouched. Staging: '+$backup) }
foreach ($record in $records) { if ((SharedHash $record.Path) -ne $record.Hash) { throw ('Source changed during processing; refusing to replace: '+$record.Path) } }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'commit.ps1') -Folder $root -RunRoot $backup -CombinedName $CombinedName -CombinedWordName $CombinedWordName
if ($LASTEXITCODE -ne 0) { throw ('Commit failed; inspect staged files and backups: '+$backup) }
foreach ($dir in @($wordStage,$pdfStage,(Join-Path $backup '.merge-stage'))) {
    foreach ($file in Get-ChildItem -LiteralPath $dir -File) { Remove-Item -LiteralPath $file.FullName }
    Remove-Item -LiteralPath $dir
}
Write-Output ('Complete. Word files: '+$records.Count+'. Centered paragraphs preserved: '+(($manifest | Measure-Object centered_preserved -Sum).Sum))
Write-Output ('First-line paragraphs indented: '+(($manifest | Measure-Object first_line_indented -Sum).Sum))
Write-Output ('PDF folder: '+$pdfOutput)
Write-Output ('Combined PDF: '+(Join-Path $pdfOutput $CombinedName))
Write-Output ('Combined Word: '+(Join-Path $root $CombinedWordName))
Write-Output ('Original backups and manifest: '+$backup)
