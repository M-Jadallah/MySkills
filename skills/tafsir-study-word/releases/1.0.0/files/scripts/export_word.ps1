param(
    [Parameter(Mandatory=$true)][string]$DocxPath,
    [Parameter(Mandatory=$true)][string]$PdfPath
)
$ErrorActionPreference = 'Stop'
$resolvedDocx = (Resolve-Path -LiteralPath $DocxPath).Path
$resolvedPdf = [System.IO.Path]::GetFullPath($PdfPath)
if ($resolvedDocx -eq $resolvedPdf) { throw 'DOCX and PDF paths must differ.' }
$pdfParent = Split-Path -Parent $resolvedPdf
[void][System.IO.Directory]::CreateDirectory($pdfParent)
$wordApp = $null
$wordDoc = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordApp.AutomationSecurity = 3
    $wordDoc = $wordApp.Documents.Open($resolvedDocx, $false, $false)
    $wordDoc.Repaginate()
    [void]$wordDoc.Fields.Update()
    foreach ($tocItem in $wordDoc.TablesOfContents) { $tocItem.Update() }
    foreach ($tocItem in $wordDoc.TablesOfContents) {
        $tocItem.Range.Font.Name = 'Traditional Arabic'
        $tocItem.Range.Font.NameBi = 'Traditional Arabic'
        $tocItem.Range.Font.Size = 20
        $tocItem.Range.Font.SizeBi = 20
        $tocItem.Range.ParagraphFormat.SpaceAfter = 0
        $tocItem.Range.ParagraphFormat.SpaceBefore = 0
        $tocItem.Range.ParagraphFormat.LineSpacingRule = 3
        $tocItem.Range.ParagraphFormat.LineSpacing = 25
        $tocItem.Range.ParagraphFormat.KeepWithNext = 0
        $tocItem.Range.ParagraphFormat.PageBreakBefore = 0
    }
    $wordDoc.Repaginate()
    foreach ($tocItem in $wordDoc.TablesOfContents) { $tocItem.UpdatePageNumbers() }
    $wordDoc.Repaginate()
    $wordDoc.Save()
    $wordDoc.ExportAsFixedFormat($resolvedPdf, 17)
    $pages = $wordDoc.ComputeStatistics(2)
    Write-Output "Updated fields and exported PDF; pages=$pages"
} finally {
    if ($null -ne $wordDoc) {
        $wordDoc.Close($false)
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordDoc)
    }
    if ($null -ne $wordApp) {
        $wordApp.Quit()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordApp)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
