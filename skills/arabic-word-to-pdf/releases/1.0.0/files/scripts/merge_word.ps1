param(
    [Parameter(Mandatory=$true)][string]$RunRoot,
    [Parameter(Mandatory=$true)][string]$PythonPath,
    [string]$CombinedWordName = 'جميع الدروس مرتبة.docx'
)
$ErrorActionPreference='Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 required' }
$run=(Resolve-Path -LiteralPath $RunRoot).Path
$manifest=@(Get-Content -LiteralPath (Join-Path $run 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json)
if (!$manifest.Count) { throw 'Empty lesson manifest' }
$stage=Join-Path $run '.word-stage'
$merge=Join-Path $run '.merge-stage'
$output=Join-Path $stage $CombinedWordName
New-Item -ItemType Directory -Path $merge -Force | Out-Null
function Plain([string]$value) { return ($value -replace '[\r\n\f\x07]','') }
function ParagraphSnapshot($p) {
    return [pscustomobject]@{Alignment=$p.Format.Alignment;ReadingOrder=$p.Format.ReadingOrder;FirstLineIndent=$p.Format.FirstLineIndent;Size=$p.Range.Font.Size;Bold=$p.Range.Font.Bold;Color=$p.Range.Font.Color;Name=$p.Range.Font.Name}
}
function VerifyParagraph($p,$wanted,[string]$label) {
    $now=ParagraphSnapshot $p
    foreach ($key in @('Alignment','ReadingOrder','FirstLineIndent','Size','Bold','Color','Name')) {
        if ($key -eq 'FirstLineIndent') {
            if ([Math]::Abs([double]$wanted.$key - [double]$now.$key) -gt 0.2) { throw ('Merged Word formatting mismatch: '+$label+' / '+$key) }
        } elseif ($wanted.$key -ne $now.$key) { throw ('Merged Word formatting mismatch: '+$label+' / '+$key) }
    }
}
$app=New-Object -ComObject Word.Application
$app.Visible=$false;$app.DisplayAlerts=0;$app.AutomationSecurity=3
$combined=$null;$expectedText='';$samples=@();$allParagraphs=@();$bookmarks=@()
try {
    for ($i=0;$i -lt $manifest.Count;$i++) {
        $name=[string]$manifest[$i].source
        $source=Join-Path $stage $name
        $original=$app.Documents.Open($source,$false,$true)
        try {
            $expectedText += Plain $original.Content.Text
            $sample=ParagraphSnapshot $original.Paragraphs.Item(1)
            $samples += $sample
            $sourceParagraphs=@()
            foreach ($p in $original.Content.Paragraphs) {
                if (($p.Range.Text -replace '[\s\x07\x0c]','').Length -eq 0) { continue }
                $sourceParagraphs += [pscustomobject]@{Text=(Plain $p.Range.Text);Format=(ParagraphSnapshot $p)}
            }
            $allParagraphs += ,$sourceParagraphs
            if ($i -eq 0) {
                $original.SaveAs2($output,12)
                $combined=$original
                $original=$null
                $mark='Lesson_001'
                [void]$combined.Bookmarks.Add($mark,$combined.Range(0,0))
            } else {
                $asDocx=Join-Path $merge (('source-{0:D3}.docx' -f ($i+1)))
                if ([IO.Path]::GetExtension($source).ToLowerInvariant() -eq '.docx') {
                    Copy-Item -LiteralPath $source -Destination $asDocx -Force
                } else {
                    $original.SaveAs2($asDocx,12)
                }
                $unique=Join-Path $merge (('unique-{0:D3}.docx' -f ($i+1)))
                $prefix=('Merge{0:D3}_' -f ($i+1))
                & $PythonPath (Join-Path $PSScriptRoot 'prepare_merge_docx.py') $asDocx $unique $prefix
                if ($LASTEXITCODE -ne 0) { throw ('Could not isolate Word styles: '+$name) }
                [void]$combined.Sections.Add()
                $start=$combined.Content.End-1
                $r=$combined.Range($start,$start)
                $r.InsertFile($unique)
                $mark=('Lesson_{0:D3}' -f ($i+1))
                [void]$combined.Bookmarks.Add($mark,$combined.Range($start,$start))
            }
            $bookmarks += $mark
        } finally { if ($null -ne $original) { $original.Close(0) } }
    }
    foreach ($sec in $combined.Sections) {
        $borderSet=$sec.Borders
        $borderSet.DistanceFrom=1
        $borderSet.DistanceFromTop=8;$borderSet.DistanceFromBottom=8
        $borderSet.DistanceFromLeft=8;$borderSet.DistanceFromRight=8
        foreach ($edge in @(-1,-2,-3,-4)) {
            $border=$borderSet.Item($edge)
            $border.LineStyle=1;$border.LineWidth=4
        }
        $footerTypes=@(1)
        if ($sec.PageSetup.DifferentFirstPageHeaderFooter) { $footerTypes += 2 }
        if ($sec.PageSetup.OddAndEvenPagesHeaderFooter) { $footerTypes += 3 }
        foreach ($footerType in $footerTypes) {
            $footer=$sec.Footers.Item($footerType)
            if ($footer.PageNumbers.Count -eq 0) { [void]$footer.PageNumbers.Add(1,$true) }
            foreach ($number in $footer.PageNumbers) { $number.Alignment=1 }
            $footer.PageNumbers.RestartNumberingAtSection=$false
        }
    }
    $combined.Save();$combined.Repaginate()
    if ((Plain $combined.Content.Text) -cne $expectedText) { throw 'Merged Word text does not equal the ordered source text' }
    $starts=@();$last=0
    for ($i=0;$i -lt $bookmarks.Count;$i++) {
        $mark=$bookmarks[$i]
        if (!$combined.Bookmarks.Exists($mark)) { throw ('Missing lesson bookmark: '+$mark) }
        $p=$combined.Bookmarks.Item($mark).Range.Paragraphs.Item(1)
        VerifyParagraph $p $samples[$i] $mark
        $page=$combined.Bookmarks.Item($mark).Range.Information(3)
        if ($page -le $last) { throw ('Lesson does not start on a later page: '+$mark) }
        $starts += $page;$last=$page
    }
    $combined.Close(0);$combined=$null
    $combined=$app.Documents.Open($output,$false,$true)
    if ((Plain $combined.Content.Text) -cne $expectedText) { throw 'Merged Word text changed after saving' }
    $combined.Repaginate()
    $preview=Join-Path $merge 'merged-word-preview.pdf'
    $combined.ExportAsFixedFormat($preview,17)
    $combined.Repaginate()
    $physicalPages=& $PythonPath -c 'from pypdf import PdfReader; import sys; print(len(PdfReader(sys.argv[1]).pages))' $preview
    if ($LASTEXITCODE -ne 0 -or [int]$physicalPages -lt $manifest.Count) { throw 'Merged Word PDF preview validation failed' }
    $starts=@();$last=0
    for ($i=0;$i -lt $bookmarks.Count;$i++) {
        $mark=$bookmarks[$i]
        if (!$combined.Bookmarks.Exists($mark)) { throw ('Lesson bookmark disappeared: '+$mark) }
        VerifyParagraph $combined.Bookmarks.Item($mark).Range.Paragraphs.Item(1) $samples[$i] $mark
        $page=$combined.Bookmarks.Item($mark).Range.Information(3)
        if ($page -le $last -or $page -gt [int]$physicalPages) { throw ('Lesson order/page break changed after saving: '+$mark) }
        $starts += $page;$last=$page
    }
    for ($i=0;$i -lt $bookmarks.Count;$i++) {
        $start=$combined.Bookmarks.Item($bookmarks[$i]).Start
        $end=$combined.Content.End
        if ($i+1 -lt $bookmarks.Count) { $end=$combined.Bookmarks.Item($bookmarks[$i+1]).Start }
        $actual=@()
        foreach ($p in $combined.Range($start,$end).Paragraphs) {
            if (($p.Range.Text -replace '[\s\x07\x0c]','').Length -eq 0) { continue }
            $actual += $p
        }
        $wanted=@($allParagraphs[$i])
        if ($actual.Count -ne $wanted.Count) { throw ('Merged Word paragraph count mismatch: '+$bookmarks[$i]) }
        for ($j=0;$j -lt $wanted.Count;$j++) {
            if ((Plain $actual[$j].Range.Text) -cne $wanted[$j].Text) { throw ('Merged Word paragraph text mismatch: '+$bookmarks[$i]+'/'+$j) }
            VerifyParagraph $actual[$j] $wanted[$j].Format ($bookmarks[$i]+'/'+$j)
        }
    }
    foreach ($sec in $combined.Sections) {
        $footerTypes=@(1)
        if ($sec.PageSetup.DifferentFirstPageHeaderFooter) { $footerTypes += 2 }
        if ($sec.PageSetup.OddAndEvenPagesHeaderFooter) { $footerTypes += 3 }
        foreach ($footerType in $footerTypes) {
            $footer=$sec.Footers.Item($footerType)
            if ($footer.PageNumbers.Count -eq 0 -or $footer.PageNumbers.RestartNumberingAtSection) { throw 'Merged Word page numbering is incomplete' }
        }
        foreach ($edge in @(-1,-2,-3,-4)) { if ($sec.Borders.Item($edge).LineStyle -ne 1) { throw 'Merged Word page border is incomplete' } }
    }
    $pages=[int]$physicalPages
    [pscustomobject]@{word_file=$CombinedWordName;lessons=$manifest.Count;pages=$pages;lesson_start_pages=$starts} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $run 'word-merge-verification.json') -Encoding UTF8
    Write-Output ('Merged Word verified: '+$manifest.Count+' lessons, '+$physicalPages+' rendered pages; Word starts '+($starts -join ','))
} finally {
    if ($null -ne $combined) { $combined.Close(0) }
    $app.Quit()
}
