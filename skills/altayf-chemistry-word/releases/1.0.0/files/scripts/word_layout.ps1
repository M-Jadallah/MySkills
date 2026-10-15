param(
  [Parameter(Mandatory=$true)][ValidateSet('export','tint')][string]$Mode,
  [Parameter(Mandatory=$true)][string]$DocumentPath,
  [string]$OutputDirectory,
  [string]$BoundsPath,
  [ValidateSet('saveas','chunks')][string]$ExportMethod='saveas'
)
$ErrorActionPreference='Stop'
$taskPath=[IO.Path]::GetFullPath($DocumentPath)
if(!(Test-Path -LiteralPath $taskPath)){throw 'DOCX not found'}
# Exclusive job lock prevents two copies of this helper from editing the same document.
$lockPath=$taskPath+'.altayf-job.lock'
$jobLock=$null;$word=$null;$doc=$null
try {
  $jobLock=[IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
  $word=New-Object -ComObject Word.Application
  $word.Visible=$false;$word.DisplayAlerts=0
  Write-Output ('Opening '+$taskPath)
  $doc=$word.Documents.Open($taskPath,$false,$false,$false)
  if($doc.ReadOnly){throw 'Word opened read-only; close your own working copy and use a new output name. Do not terminate user Word.'}
  Write-Output 'Repaginating'
  $doc.Repaginate()
  if($Mode -eq 'tint') {
    if(!$BoundsPath){throw 'BoundsPath required'}
    $bounds=Get-Content -LiteralPath $BoundsPath -Encoding UTF8 -Raw | ConvertFrom-Json
    for($i=$doc.Shapes.Count;$i -ge 1;$i--) {
      $shape=$doc.Shapes.Item($i)
      if($shape.Name -like 'AltayfCard*_transparent_background'){$shape.Delete()}
    }
    foreach($card in $bounds) {
      if(!$doc.Bookmarks.Exists($card.name)){throw ('Missing bookmark '+$card.name)}
      $anchor=$doc.Bookmarks.Item($card.name).Range.Duplicate;$anchor.Collapse(1)
      if($anchor.Information(3) -ne $card.page){throw ('Bookmark page drift '+$card.name+'; recompute geometry')}
      $shape=$doc.Shapes.AddShape(1,$card.left,$card.top,$card.width,$card.height,$anchor)
      $shape.LayoutInCell=$false;$shape.RelativeHorizontalPosition=1;$shape.RelativeVerticalPosition=1
      $shape.Left=$card.left;$shape.Top=$card.top;$shape.WrapFormat.Type=5;$shape.LockAnchor=$true
      $shape.Line.Visible=0;$shape.Shadow.Visible=0;$shape.Fill.Visible=-1;$shape.Fill.Solid()
      $shape.Fill.ForeColor.RGB=$card.rgb;$shape.Fill.Transparency=0.94;$shape.ZOrder(5)
      $shape.Name=$card.name+'_transparent_background'
    }
    $doc.Repaginate();$doc.Saved=$false;$doc.Save();Write-Output ('Applied '+$bounds.Count+' fills at 94 percent transparency')
  } else {
    if(!$OutputDirectory){throw 'OutputDirectory required'}
    $qaPath=[IO.Path]::GetFullPath($OutputDirectory)
    $null=New-Item -ItemType Directory -Force -Path $qaPath
    if((Get-ChildItem -LiteralPath $qaPath -Filter '*.pdf').Count -gt 0){throw 'Use a fresh export directory; old PDF chunks must never contaminate this pass'}
    Write-Output 'Updating fields'
    $null=$doc.Fields.Update();$doc.Repaginate()
    Write-Output 'Saving'
    $doc.Saved=$false;$doc.Save();$pages=$doc.ComputeStatistics(2)
    Write-Output ('Pages '+$pages)
    # Render a freshly loaded, saved document. Word's in-memory tree can retain
    # stale layout/tagging state after an OOXML import even when Save normalizes it.
    $doc.Close($false);[Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc)|Out-Null
    $doc=$null
    $doc=$word.Documents.Open($taskPath,$false,$true,$false)
    Write-Output 'Reopened saved DOCX for native PDF rendering'
    if($ExportMethod -eq 'saveas') {
      # Native PDF SaveAs avoids an observed ExportAsFixedFormat hang on the retained frame.
      # Save the editable DOCX first. Close without saving the PDF-backed document afterwards.
      $pdf=Join-Path $qaPath ('pages-{0:D4}-{1:D4}.pdf' -f 1,$pages)
      $doc.SaveAs2($pdf,17)
    } else {
      for($first=1;$first -le $pages;$first+=10) {
        $last=[Math]::Min($first+9,$pages);$pdf=Join-Path $qaPath ('pages-{0:D4}-{1:D4}.pdf' -f $first,$last)
        $doc.ExportAsFixedFormat($pdf,17,$false,0,3,$first,$last)
      }
    }
    Write-Output ('Exported '+$pages+' pages to '+$qaPath)
  }
} finally {
  if($null -ne $doc){$doc.Close($false);[Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc)|Out-Null}
  if($null -ne $word){$word.Quit();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)|Out-Null}
  if($null -ne $jobLock){$jobLock.Dispose();Remove-Item -LiteralPath $lockPath}
}

