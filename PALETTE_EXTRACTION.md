# Palette extraction workflow

End-to-end recipe for sampling SSMS's Spatial Results palette into a machine-readable CSV. Run on a Windows box with SSMS + PowerShell 5+.

The bigger the grid, the more samples per run. With the script doing the eyedropping there's no reason not to push it — 32×32 (1024 cells) gives a comfortable margin for an 8-bit (256-colour) target palette.

## 1. Render the probe

1. Open [`Colour palette.sql`](Colour%20palette.sql) in SSMS.
2. Scroll to the last batch (the one starting `/*Scriptable palette probe.`).
3. (Optional) bump `@grid_size` higher if you want denser sampling — 32, 48, 64 all work. Cell pitch is fixed at 3 units, so total grid edge = `3 * @grid_size` spatial units.
4. Highlight just that batch, F5.
5. Click **Spatial Results**. Maximise SSMS, maximise the pane.

## 2. Capture the screenshot

1. Press **Win+Shift+S** (Snipping Tool), drag a tight crop around all the cells — include the overlap strip at the bottom.
2. Save into the repo root as `palette4.png`.
3. Avoid letterboxing — keep the crop tight to the cells so calibration is easier, but it's fine to include a couple of axis ticks for reference.

## 3. Find calibration coordinates

You need **three** numbers:
- `X0, Y0` — pixel coords of the **centre** of the bottom-left cell (spatial col=0, row=0).
- `X1, Y1` — pixel coords of the **centre** of the top-right cell (spatial col=N-1, row=N-1).
- `OverlapY` — pixel y of the overlap strip's row centre.

The fastest way:
1. Open `palette4.png` in **Paint** (right-click → Open with → Paint).
2. Hover over the centre of each cell. Pixel coordinates show in the **bottom-left status bar**.
3. Jot the four pairs down.

The bottom-left cell of the singleton grid is the one *immediately above* the overlap strip, leftmost column. The top-right is the cell at the far top-right corner of the grid.

**My Values from image**
61, 1463
1489, 36
1508
## 4. Run the extractor

Open PowerShell in the repo root:

```powershell
.\extract-palette.ps1 `
    -Image .\palette4.png `
    -X0 61 -Y0 1463 `
    -X1 1489 -Y1 36 `
    -OverlapY 1508 `
    -OutCsv .\palette-extract.csv
```

Substitute your actual coordinates. The script:
- Loads the image via `System.Drawing.Bitmap` (no external deps).
- **Auto-detects `GridSize`** by scanning a horizontal line between `X0..X1` at `y = Y0` and counting cell transitions.  Pass `-GridSize N` to override if auto-detect mis-counts.
- Linearly interpolates every cell centre from the two calibration points.
- Reads the centre RGB of each cell.
- Outputs CSV.

Sample CSV row:
```
idx,R,G,B,hex,kind,col,row
1,194,219,217,#C2DBD9,singleton,0,0
2,224,180,140,#E0B48C,singleton,1,0
...
1025-1026,108,98,82,#6C6252,overlap_pair,0,-1
```

## 5. Sanity check

Open `palette-extract.csv` in Excel or a text editor. Spot-check:
- 1024 singleton rows (or `@grid_size`²) + 32 overlap rows (or `@grid_size`).
- `idx=1` should match the bottom-left cell you can see in the screenshot.
- RGB values should be in the 100–250 range (SSMS uses pastels).

If a row is `255,255,255` (pure white), the script sampled outside a cell — your calibration is off. Re-check the coordinates, especially `Y0` vs `Y1` (Y0 is the LARGER pixel value because screen Y grows downward while spatial Y grows upward).

## 6. Commit and ping me

```powershell
git add palette4.png palette-extract.csv
git commit -m "Palette extraction sample (grid=32)"
git push
```

I'll build:
- `dbo.fn_SsmsPaletteColour(@row_idx INT) RETURNS CHAR(7)` — row idx → `#rrggbb`.
- `dbo.fn_NearestSsmsRecipe(@target_hex CHAR(7))` — target hex → recommended single or layered row positions.
- A quantisation hook for the SVG conversion that picks row positions to match an 8-bit target palette.

## Tips for denser sampling

- A larger `@grid_size` is free except for screenshot resolution.  Sampling 4096 cells (64×64) gives a much richer base set.  The script just interpolates more points; no extra calibration work.
- You can re-render the same shape multiple times at the same spatial position to deepen saturation — each extra row halves the remaining white component.  If you want to map this, drop a few **triple-stack** test cells in next to the overlap strip and we'll add columns to capture them.
- On a 4K monitor the cells stay readable up to ~96×96 (≈9000 samples).  Cell size in pixels = `screen_px / (3 * @grid_size + 6)` roughly.
