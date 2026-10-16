# Dot-source from run.ps1. Bookmarks are added only after Save, then discarded on Close(0).
function NavigationText([string]$value) {
    return (($value -replace '[\r\n\f\x07]','').Trim())
}

function Export-NavigablePDF($doc, [string]$source, [string]$pdfPath, $plan) {
    $headings=@();$title='';$explicit=$null
    if ($null -ne $plan) {
        $matches=@($plan.lessons | Where-Object { $_.source -ceq $source })
        if ($matches.Count -gt 1) { throw ('Duplicate navigation plan entry: '+$source) }
        if ($matches.Count -eq 1) { $explicit=$matches[0] }
    }
    if ($null -ne $explicit) {
        $title=NavigationText ([string]$explicit.title)
        $last=0
        foreach ($h in @($explicit.headings)) {
            $index=[int]$h.paragraph;$level=[int]$h.level
            if ($index -le $last -or $index -gt $doc.Paragraphs.Count -or $level -lt 1 -or $level -gt 9) { throw ('Invalid navigation heading order/level: '+$source) }
            $p=$doc.Paragraphs.Item($index)
            $text=NavigationText $p.Range.Text
            if (!$text -or $text -cne (NavigationText ([string]$h.text))) { throw ('Navigation heading text does not match paragraph '+$index+': '+$source) }
            $headings += [pscustomobject]@{title=$text;level=$level;paragraph=$index}
            $last=$index
        }
    } else {
        $index=0;$meaningful=0
        foreach ($p in $doc.Paragraphs) {
            $index++;$text=NavigationText $p.Range.Text
            if (!$text) { continue }
            $meaningful++
            $level=[int]$p.Format.OutlineLevel
            # Word Title is not an outline level. It can still supply the lesson title.
            if (!$title -and $meaningful -le 10 -and $p.Style.NameLocal -eq $doc.Styles.Item(-63).NameLocal) { $title=$text }
            if ($level -ge 1 -and $level -le 9) {
                if (!$title -and $headings.Count -eq 0 -and $meaningful -le 10 -and $level -le 2) { $title=$text }
                $headings += [pscustomobject]@{title=$text;level=$level;paragraph=$index}
            }
        }
    }
    if (!$title) { $title=([IO.Path]::GetFileNameWithoutExtension($source) -replace '^\s*[0-9٠-٩۰-۹]+[\s._()\-–—]*','').Trim() }
    if (!$title) { throw ('Missing lesson title; supply navigation plan: '+$source) }
    # The lesson itself represents an initial heading equal to its title; retain its children.
    if ($headings.Count -gt 0 -and $headings[0].title -ceq $title) { $headings=@($headings | Select-Object -Skip 1) }
    $prefix='CodexNav_'+[guid]::NewGuid().ToString('N').Substring(0,8)
    $rootMark=$prefix+'_Start'
    [void]$doc.Bookmarks.Add($rootMark,$doc.Range(0,0))
    $i=0
    foreach ($h in $headings) {
        $i++;$name=$prefix+('_H{0:D5}' -f $i)
        $p=$doc.Paragraphs.Item($h.paragraph)
        $r=$p.Range.Duplicate
        $r.Collapse(1)
        [void]$doc.Bookmarks.Add($name,$r)
        $h | Add-Member -NotePropertyName bookmark -NotePropertyValue $name
    }
    # wdExportCreateWordBookmarks=2 exports exact destinations without changing heading styles.
    $doc.ExportAsFixedFormat($pdfPath,17,$false,0,0,1,1,0,$true,$true,2)
    if ($headings.Count -eq 0) { Write-Warning ('No topic headings found; review navigation plan for: '+$source) }
    return [pscustomobject]@{title=$title;bookmark=$rootMark;headings=@($headings);planned=($null -ne $explicit)}
}
