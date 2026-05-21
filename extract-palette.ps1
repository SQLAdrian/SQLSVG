<#
.SYNOPSIS
    Extract SSMS Spatial Results palette colours from a screenshot of the
    Colour palette.sql probe output.

.DESCRIPTION
    Reads an NxN singleton grid plus an optional N-cell overlap strip.
    Outputs CSV: idx, R, G, B, hex, kind (singleton | overlap_pair).
    Result-row ordering matches the SQL probe: bottom-left = row 1,
    scanning right then up.

    Two calibration points define the grid's pixel mapping:
      (X0, Y0) = pixel centre of the BOTTOM-LEFT cell  (col=0, row=0).
      (X1, Y1) = pixel centre of the TOP-RIGHT cell    (col=N-1, row=N-1).
    Linear interpolation handles cells in between.  Y0 > Y1 because
    screen pixel Y grows downward while SSMS spatial Y grows upward.

    Overlap strip is sampled if -OverlapY is supplied; cells are at
    pixel x = (X0 + j * (X1-X0)/(N-1)) for j in 0..N-1.

.PARAMETER Image
    Path to the PNG screenshot (cropped to just the cells is fine but
    not required).

.PARAMETER GridSize
    N, where the singleton grid is NxN.  Must match @grid_size in
    Colour palette.sql.  If omitted, auto-detected by counting cells
    at y=Y0 between X0..X1.

.PARAMETER X0
    Pixel x of the centre of the BOTTOM-LEFT singleton cell.

.PARAMETER Y0
    Pixel y of the same cell (typically a LARGE number — close to image
    height).

.PARAMETER X1
    Pixel x of the centre of the TOP-RIGHT singleton cell.

.PARAMETER Y1
    Pixel y of the same cell (typically a SMALL number — close to top
    of image).

.PARAMETER OverlapY
    Pixel y of the overlap strip's row centre.  If omitted, the strip
    is skipped.

.PARAMETER OutCsv
    Output CSV path.  Default: .\palette-extract.csv

.EXAMPLE
    # Auto-detect grid size from the screenshot:
    .\extract-palette.ps1 -Image .\palette4.png `
        -X0 61 -Y0 1463 -X1 1489 -Y1 36 -OverlapY 1508 `
        -OutCsv .\palette-extract.csv

.EXAMPLE
    # Force grid size if auto-detect mis-counts (e.g., heavy anti-aliasing):
    .\extract-palette.ps1 -Image .\palette4.png -GridSize 64 `
        -X0 61 -Y0 1463 -X1 1489 -Y1 36 -OverlapY 1508 `
        -OutCsv .\palette-extract.csv
#>
param(
    [Parameter(Mandatory=$true)] [string]$Image,
    [int]$GridSize = 0,
    [Parameter(Mandatory=$true)] [int]$X0,
    [Parameter(Mandatory=$true)] [int]$Y0,
    [Parameter(Mandatory=$true)] [int]$X1,
    [Parameter(Mandatory=$true)] [int]$Y1,
    [int]$OverlapY = -1,
    [string]$OutCsv = ".\palette-extract.csv"
)

Add-Type -AssemblyName System.Drawing

$path = (Resolve-Path -LiteralPath $Image).Path
$img  = [System.Drawing.Bitmap]::FromFile($path)
Write-Host ("Image loaded: {0} ({1} x {2})" -f $path, $img.Width, $img.Height)

#auto-detect grid size if not specified: scan a horizontal line between X0..X1
#at Y=Y0, count transitions from white background into coloured cells.
if ($GridSize -le 0) {
    $whiteThresh = 245
    $count = 0
    $inCell = $false
    $xLo = [Math]::Min($X0, $X1); $xHi = [Math]::Max($X0, $X1)
    for ($x = $xLo; $x -le $xHi; $x++) {
        $c = $img.GetPixel($x, $Y0)
        $avg = ($c.R + $c.G + $c.B) / 3
        if ($avg -lt $whiteThresh -and -not $inCell) { $count++; $inCell = $true }
        elseif ($avg -ge $whiteThresh) { $inCell = $false }
    }
    if ($count -lt 2) { throw "Auto-detect failed: only $count cells found at y=$Y0.  Check calibration." }
    $GridSize = $count
    Write-Host ("Auto-detected GridSize = {0} (scanned y={1} between x={2}..{3}).  Pass -GridSize explicitly to override." -f $GridSize, $Y0, $xLo, $xHi)
}

if ($GridSize -lt 2) { throw "GridSize must be >= 2" }
$xStep = ($X1 - $X0) / [double]($GridSize - 1)
$yStep = ($Y1 - $Y0) / [double]($GridSize - 1)

$rows = New-Object System.Collections.Generic.List[string]
$rows.Add("idx,R,G,B,hex,kind,col,row")

#singletons - result-row order matches the SQL probe: idx = row*N + col + 1
$idx = 1
for ($row = 0; $row -lt $GridSize; $row++) {
    for ($col = 0; $col -lt $GridSize; $col++) {
        $px = [int][Math]::Round($X0 + $col * $xStep)
        $py = [int][Math]::Round($Y0 + $row * $yStep)
        if ($px -lt 0 -or $px -ge $img.Width -or $py -lt 0 -or $py -ge $img.Height) {
            Write-Warning ("Cell ({0},{1}) sample at ({2},{3}) is outside image bounds; using clamp." -f $col,$row,$px,$py)
            $px = [Math]::Max(0, [Math]::Min($img.Width - 1, $px))
            $py = [Math]::Max(0, [Math]::Min($img.Height - 1, $py))
        }
        $p   = $img.GetPixel($px, $py)
        $hex = "#{0:X2}{1:X2}{2:X2}" -f $p.R, $p.G, $p.B
        $rows.Add(("{0},{1},{2},{3},{4},singleton,{5},{6}" -f $idx,$p.R,$p.G,$p.B,$hex,$col,$row))
        $idx++
    }
}

#overlap pairs (one composite sample per cell - the visible blend)
if ($OverlapY -ge 0) {
    for ($j = 0; $j -lt $GridSize; $j++) {
        $px = [int][Math]::Round($X0 + $j * $xStep)
        $py = [int]$OverlapY
        $px = [Math]::Max(0, [Math]::Min($img.Width - 1, $px))
        $py = [Math]::Max(0, [Math]::Min($img.Height - 1, $py))
        $p   = $img.GetPixel($px, $py)
        $hex = "#{0:X2}{1:X2}{2:X2}" -f $p.R, $p.G, $p.B
        $bot = $GridSize * $GridSize + 2 * $j + 1
        $top = $bot + 1
        $rows.Add(("{0}-{1},{2},{3},{4},{5},overlap_pair,{6},-1" -f $bot,$top,$p.R,$p.G,$p.B,$hex,$j))
    }
}

$img.Dispose()
$rows -join "`r`n" | Out-File -Encoding utf8 -FilePath $OutCsv
Write-Host ("Wrote {0} data rows to {1}" -f ($rows.Count - 1), (Resolve-Path -LiteralPath $OutCsv).Path)
