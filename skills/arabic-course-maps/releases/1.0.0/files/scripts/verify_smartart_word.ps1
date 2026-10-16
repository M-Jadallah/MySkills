param([Parameter(Mandatory=$true)][string]$InputDoc,[Parameter(Mandatory=$true)][string]$ReportJson,[string]$EditSmokeOutput)
$ErrorActionPreference='Stop'
$InputDoc=(Resolve-Path -LiteralPath $InputDoc).ProviderPath
if($EditSmokeOutput) {
    if(-not [IO.Path]::IsPathRooted($EditSmokeOutput)){$EditSmokeOutput=Join-Path (Get-Location).Path $EditSmokeOutput}
    $EditSmokeOutput=[IO.Path]::GetFullPath($EditSmokeOutput)
    if($EditSmokeOutput -eq $InputDoc){throw 'The edit smoke test must use a separate scratch output.'}
}
$application=$null;$document=$null
try {
    $application=New-Object -ComObject Word.Application
    $application.Visible=$false;$application.DisplayAlerts=0;$application.AutomationSecurity=3
    $document=$application.Documents.Open($InputDoc,$false,$true,$false)
    $panels=@()
    foreach($shape in $document.InlineShapes) {
        if($shape.HasSmartArt -ne -1){throw 'A main-document inline graphic is not genuine SmartArt.'}
        $levels=@();$text=@()
        for($i=1;$i -le $shape.SmartArt.AllNodes.Count;$i++) {
            $node=$shape.SmartArt.AllNodes.Item($i)
            $levels += $node.Level
            $text += $node.TextFrame2.TextRange.Text
        }
        $panels += [pscustomobject]@{LayoutId=$shape.SmartArt.Layout.Id;NodeCount=$shape.SmartArt.AllNodes.Count;Levels=$levels;Text=$text}
    }
    $editable=$null
    if($EditSmokeOutput) {
        if($document.InlineShapes.Count -eq 0){throw 'No SmartArt to edit.'}
        $sa=$document.InlineShapes.Item(1).SmartArt
        $before=$sa.AllNodes.Count
        $node=$sa.AllNodes.Item(1).AddNode(5,1)
        $node.TextFrame2.TextRange.Text='SmartArt edit smoke test'
        $editable=$sa.AllNodes.Count -eq ($before+1)
        if(-not $editable){throw 'Native SmartArt editing failed.'}
        $document.SaveAs2($EditSmokeOutput,16)
    }
    [pscustomobject]@{NativeSmartArtCount=$panels.Count;Panels=$panels;NativeEditSucceeded=$editable} | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $ReportJson -Encoding UTF8
    Write-Output ('Verified genuine SmartArt in Word: '+$panels.Count+'; native edit test: '+$editable)
}finally {
    if($document){$document.Close(0);[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)}
    if($application){$application.Quit();[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($application)}
    [GC]::Collect();[GC]::WaitForPendingFinalizers()
}
