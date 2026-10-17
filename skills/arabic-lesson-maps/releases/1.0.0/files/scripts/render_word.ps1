param([Parameter(Mandatory=$true)][string]$InputDoc, [Parameter(Mandatory=$true)][string]$PdfOut)
$ErrorActionPreference = 'Stop'
$lessonWord = $null
$lessonDocument = $null
try {
    $lessonWord = New-Object -ComObject Word.Application
    $lessonWord.Visible = $false
    $lessonWord.DisplayAlerts = 0
    $lessonWord.AutomationSecurity = 3
    $lessonDocument = $lessonWord.Documents.Open($InputDoc, $false, $true, $false)
    $lessonDocument.Repaginate()
    $lessonDocument.ExportAsFixedFormat($PdfOut, 17)
    Write-Output ('Exported ' + $lessonDocument.ComputeStatistics(2) + ' pages')
} finally {
    if ($null -ne $lessonDocument) {
        $lessonDocument.Close(0)
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($lessonDocument)
    }
    if ($null -ne $lessonWord) {
        $lessonWord.Quit()
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($lessonWord)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
