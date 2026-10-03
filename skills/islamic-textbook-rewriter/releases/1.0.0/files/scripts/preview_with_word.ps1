param(
    [Parameter(Mandatory = $true)][string]$InputDocx,
    [string]$OutputPdf
)

# Optional Windows preview: opens only this input read-only, without saving it.
$ErrorActionPreference = 'Stop'
$previewInput = (Resolve-Path -LiteralPath $InputDocx).Path
if ([System.IO.Path]::GetExtension($previewInput) -ne '.docx') {
    throw 'Expected a .docx input.'
}
if (-not $OutputPdf) {
    $OutputPdf = [System.IO.Path]::ChangeExtension($previewInput, '.preview.pdf')
}
$previewOutput = [System.IO.Path]::GetFullPath($OutputPdf)
if ([System.IO.Path]::GetExtension($previewOutput) -ne '.pdf') {
    throw 'Expected a .pdf output.'
}
$previewFolder = [System.IO.Path]::GetDirectoryName($previewOutput)
[void][System.IO.Directory]::CreateDirectory($previewFolder)
$previewWord = $null
$previewDoc = $null
try {
    $previewWord = New-Object -ComObject Word.Application
    $previewWord.Visible = $false
    $previewWord.DisplayAlerts = 0
    $previewWord.AutomationSecurity = 3
    $previewDoc = $previewWord.Documents.Open($previewInput, $false, $true)
    $previewDoc.Repaginate()
    $previewShapes = @()
    foreach ($previewShape in $previewDoc.InlineShapes) {
        $previewIsMap = $previewShape.HasSmartArt -ne 0
        $previewShapes += @{
            type = $previewShape.Type
            smartart = $previewIsMap
            nodes = $(if ($previewIsMap) { $previewShape.SmartArt.AllNodes.Count } else { 0 })
        }
    }
    $previewDoc.ExportAsFixedFormat($previewOutput, 17)
    @{
        ok = $true
        pdf = $previewOutput
        pages = $previewDoc.ComputeStatistics(2)
        shapes = $previewShapes
    } | ConvertTo-Json -Depth 5
} finally {
    if ($null -ne $previewDoc) { $previewDoc.Close(0) }
    if ($null -ne $previewWord) { $previewWord.Quit() }
    if ($null -ne $previewDoc) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($previewDoc) }
    if ($null -ne $previewWord) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($previewWord) }
}
