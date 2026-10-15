param([Parameter(Mandatory=$true)][string]$PlanJson,[Parameter(Mandatory=$true)][string]$OutputDoc)
$ErrorActionPreference='Stop'

function Get-OfficeColor([string]$Hex) {
    $red=[Convert]::ToInt32($Hex.Substring(0,2),16)
    $green=[Convert]::ToInt32($Hex.Substring(2,2),16)
    $blue=[Convert]::ToInt32($Hex.Substring(4,2),16)
    return $red+($green -shl 8)+($blue -shl 16)
}

function Set-NodeContent($NativeNode,$NodeData,[int]$Level,$Design,[bool]$Hierarchy) {
    $label=$NodeData.label
    if($NodeData.relation){$label=$NodeData.relation+"`r"+$label}
    $textFrame=$NativeNode.TextFrame2
    $textFrame.TextRange.Text=$label
    $textFrame.WordWrap=-1
    $textFrame.VerticalAnchor=3
    $textFrame.MarginTop=5; $textFrame.MarginBottom=5
    $textFrame.MarginLeft=7; $textFrame.MarginRight=7
    $range=$textFrame.TextRange
    $range.Font.Name=$Design.font
    $range.Font.NameComplexScript=$Design.font
    $range.Font.NameFarEast=$Design.font
    $range.Font.Size=$Design.sizes_pt.diagram
    $range.Font.Bold=0
    if($Level -le 1){$range.Font.Bold=-1}
    $range.ParagraphFormat.Alignment=2
    if($Hierarchy){$NativeNode.OrgChartLayout=1}
    if($Level -eq 0){$fill=$Design.colors.primary;$ink=$Design.colors.white}
    elseif($Level -eq 1){$fill=$Design.colors.secondary;$ink=$Design.colors.white}
    else{$fill=$Design.colors.tint;$ink=$Design.colors.ink}
    $range.Font.Fill.ForeColor.RGB=Get-OfficeColor $ink
    $NativeNode.Shapes.Fill.Solid()
    $NativeNode.Shapes.Fill.ForeColor.RGB=Get-OfficeColor $fill
    $NativeNode.Shapes.Line.Visible=0
    if($NodeData.relation){$range.Paragraphs(1,1).Font.Size=$Design.sizes_pt.small}
}

function Add-Branch($NativeNode,$NodeData,[int]$Level,$Design) {
    Set-NodeContent $NativeNode $NodeData $Level $Design $true
    $previous=$null
    foreach($child in $NodeData.children) {
        if($null -eq $previous){$added=$NativeNode.AddNode(5,1)}else{$added=$previous.AddNode(2,1)}
        Add-Branch $added $child ($Level+1) $Design
        $previous=$added
    }
}

$word=$null;$document=$null
try {
    $plan=Get-Content -LiteralPath $PlanJson -Raw -Encoding UTF8 | ConvertFrom-Json
    $word=New-Object -ComObject Word.Application
    $word.Visible=$false
    $word.DisplayAlerts=0
    $word.AutomationSecurity=3
    $document=$word.Documents.Add()
    if($word.SmartArtLayouts.Count -eq 0){throw 'Native Word SmartArt layouts are unavailable.'}
    $count=0
    foreach($panel in $plan.panels) {
        if($count -gt 0){$document.Range($document.Content.End-1,$document.Content.End-1).InsertBreak(7)}
        $anchor=$document.Paragraphs.Last.Range
        $layout=$word.SmartArtLayouts.Item($panel.layout_id)
        $graphic=$document.Shapes.AddSmartArt($layout,0,0,[single]$panel.width_pt,[single]$panel.height_pt,$anchor)
        $graphic.Name='lm_smartart_'+$panel.id
        $smartArt=$graphic.SmartArt
        $smartArt.QuickStyle=$word.SmartArtQuickStyles.Item($plan.design.smartart.quick_style_id)
        if($panel.kind -ne 'sequence'){$smartArt.Reverse=-1}
        while($smartArt.AllNodes.Count -gt 1){$smartArt.AllNodes.Item($smartArt.AllNodes.Count).Delete()}
        if($panel.kind -eq 'tree' -or $panel.kind -eq 'decision') {
            Add-Branch $smartArt.AllNodes.Item(1) $panel.root 0 $plan.design
        } else {
            $previous=$null
            for($i=0;$i -lt $panel.nodes.Count;$i++) {
                if($i -eq 0){$node=$smartArt.AllNodes.Item(1)}else{$node=$previous.AddNode(2,1)}
                Set-NodeContent $node $panel.nodes[$i] $(if($i -eq 0){0}else{1}) $plan.design $false
                $previous=$node
            }
        }
        if($graphic.HasSmartArt -ne -1){throw 'Office did not create a genuine SmartArt graphic.'}
        $inline=$graphic.ConvertToInlineShape()
        if($inline.HasSmartArt -ne -1){throw 'Inline conversion lost native SmartArt.'}
        $count++
        Write-Output ('Created native SmartArt '+$count+'/'+$plan.panels.Count+': '+$panel.id)
    }
    $document.Repaginate()
    $document.SaveAs2($OutputDoc,16)
    if($document.InlineShapes.Count -ne $plan.panels.Count){throw 'SmartArt panel count mismatch.'}
} finally {
    if($document){$document.Close(0);[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)}
    if($word){$word.Quit();[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)}
    [GC]::Collect();[GC]::WaitForPendingFinalizers()
}
