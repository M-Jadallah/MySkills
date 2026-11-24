param(
    [Parameter(Mandatory=$true)][string]$DocumentPath,
    [Parameter(Mandatory=$true)][string]$PdfPath,
    [Parameter(Mandatory=$true)][string]$ReportPath
)
$ErrorActionPreference = 'Stop'
$docTarget = [System.IO.Path]::GetFullPath($DocumentPath)
$pdfTarget = [System.IO.Path]::GetFullPath($PdfPath)
$reportTarget = [System.IO.Path]::GetFullPath($ReportPath)
if (-not (Test-Path -LiteralPath $docTarget -PathType Leaf)) { throw 'The input document does not exist.' }
if ($docTarget -eq $pdfTarget -or $docTarget -eq $reportTarget) { throw 'Export paths must differ from the document.' }
New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($pdfTarget)),([System.IO.Path]::GetDirectoryName($reportTarget)) | Out-Null
$wordApp = $null
$wordDoc = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordDoc = $wordApp.Documents.Open($docTarget,$false,$false)
    $wordDoc.Fields.Update() | Out-Null
    $wordDoc.Repaginate()
    $wordDoc.Save()
    $pageCount = $wordDoc.ComputeStatistics(2)
    $wordDoc.ExportAsFixedFormat($pdfTarget,17)
    $pageInfo = @()
    for ($page = 1; $page -le $pageCount; $page++) {
        $pageStart = $wordDoc.GoTo(1,1,$page).Start
        if ($page -lt $pageCount) { $pageEnd = $wordDoc.GoTo(1,1,($page+1)).Start } else { $pageEnd = $wordDoc.Content.End }
        $pageInfo += [PSCustomObject]@{page=$page;start=$pageStart;end=$pageEnd;text=$wordDoc.Range($pageStart,$pageEnd).Text}
    }
    [PSCustomObject]@{pages=$pageCount;pageInfo=$pageInfo} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $reportTarget -Encoding utf8
    Write-Output "Exported $pageCount pages with Microsoft Word."
} finally {
    if ($null -ne $wordDoc) { $wordDoc.Close(0) }
    if ($null -ne $wordApp) { $wordApp.Quit() }
    if ($null -ne $wordDoc) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wordDoc) }
    if ($null -ne $wordApp) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp) }
    [GC]::Collect()
}
