# SQLSVG

Render any SVG inside SQL Server Management Studio's Spatial Results tab — pure T-SQL, no CLR, no PowerShell, no external converters. Drop an SVG path into the script, hit F5, look at the spatial tab.

## The bigger picture

The original recipe — written up at [sqldba.org: Drawing in SQL Server using SSMS](https://www.sqldba.org/post/drawing-in-sql-server-using-ssms-a-technical-article) — goes roughly like this:

1. **Take an image** (a photo, a logo, a sketch).
2. **Vectorise** it in Inkscape — trace the bitmap, turn it into paths.
3. **Clean up** the SVG: straighten curves, prune fiddly nodes, simplify down to ~10 colour layers.
4. **Convert** each path's `d` attribute to Well-Known Text using an external tool like MyGeoData, scaling the SVG to ~80–90% first to leave headroom.
5. **Paste** the resulting WKT into a T-SQL script, one polygon per row, ordered carefully so SSMS's per-row palette lands the colour you want on the layer you want.
6. **Run** it. SSMS's Spatial Results tab paints each row in its own opaque colour. Overlapping rows mix visually into composite tones — that's how shading is "faked".

That blog post ate roughly 100 hours of an afternoon. Most of those hours weren't spent drawing — they were spent in steps 3, 4 and 5: Inkscape, an external WKT converter, and a lot of copy-paste into SQL.

**SQLSVG bypasses step 4 entirely.** Drop the SVG into a stored procedure call, and it parses the paths, flattens the curves, applies any nested transforms, and hands back one `geometry` row per shape — ready for the spatial tab. No external converter, no paste-as-literal pipeline.

What it does **not** do is replace step 3. Vector prep in Inkscape (or your editor of choice) is still where most of the artistic decisions happen — picking which paths belong together, deciding how many layers you can spend, simplifying intricate curves so the spatial tab can render them. SQLSVG just stops the conversion step from being the bottleneck.

And the colour question still belongs to SSMS. The spatial tab assigns colours by row order, not by anything you say in the data — so colouring is a matter of placing rows in the right sequence and using overlap to mix opaque tones into the shades you actually want. See [`Brent/brent.sql`](Brent/brent.sql) for a worked example of that technique, and [`Colour palette.sql`](Colour%20palette.sql) for the palette-probe scripts.

## What it does

Parses the SVG `<path>` `d` attribute (all 20 commands: `M m L l H h V v C c S s Q q T t A a Z z`), composes nested `<g transform="...">` chains up to 8 deep, flattens Béziers and elliptical arcs, builds POLYGON / MULTIPOLYGON WKT, and returns one `geometry` row per path.

## Quick start

1. Run [`SVG_to_Geometry.sql`](SVG_to_Geometry.sql) — installs three TVFs (`fn_TokenizeSvgPath`, `fn_ParseSvgPath`, `fn_ParseSvgTransform`) and runs the example.
2. Run [`SVG_to_Geometry_Proc.sql`](SVG_to_Geometry_Proc.sql) — installs the wrapper procedure.
3. Try a sample:

```sql
EXEC dbo.SVG_to_Geometry N'C:\Github\SQLSVG\Test\Simple.svg';
```

Click the **Spatial results** tab in SSMS.

## Procedure parameters

| Parameter | Default | Effect |
|-----------|---------|--------|
| `@svg_path` | — | Absolute path to the `.svg` file (`OPENROWSET BULK` requires a literal). |
| `@flatten_steps` | `12` | Line segments per Bézier / arc. Higher = smoother + more points. |
| `@single_layer` | `0` | `1` = `UnionAggregate` everything into one row (one shape, one colour). Complex SVGs can produce a geometry the spatial tab refuses to render — leave at `0` for those. |
| `@emit_script` | `0` | `1` = emit ready-to-paste `INSERT INTO @tt(label, gg) VALUES (..., geometry::STGeomFromText('...', 0));` lines instead of geometry rows. Useful for stashing parsed geometry into a [brent.sql](Brent/brent.sql)-style script. |

## Output columns

| Column | Notes |
|--------|-------|
| `layer_id` | Row number, one per `<path>`. |
| `group_label` | Nearest-ancestor `<g>`'s `inkscape:label` if set, else its `id`. SSMS Spatial tab uses the first text column as the label. |
| `path_id` | `<path id="...">` value. |
| `fill_hex` | Resolved from inline `style="fill:..."`, then `fill="..."`, then CSS class. NULL if inherited from an ancestor `<g>`. |
| `geom` | `geometry` (SRID 0). Y is negated so the picture renders upright in SSMS. |

## Samples

| Path | Source |
|------|--------|
| [`Test/Simple.svg`](Test/Simple.svg) | NZ Manufactured seal — curved text + kiwi figure. The original test case. |
| [`Test/SQL Server.svg`](Test/SQL Server.svg) | SQL Server logo. |
| [`Test/Santa 2019.svg`](Test/Santa 2019.svg) | Santa illustration. Big — try `@flatten_steps = 6`. |
| [`Brent/Brent.svg`](Brent/Brent.svg) | Brent Ozar caricature, an homage to Michael J. Swart's "draw in SSMS" series. |
| [`Emmet/Emmet.svg`](Emmet/Emmet.svg) | LEGO Movie 2's Emmet. |
| [`ThisIsFine/This is fine.svg`](ThisIsFine/This%20is%20fine.svg) | The dog. |

## Known limits

- Only `<path>` is parsed. `<rect>`, `<circle>`, `<ellipse>`, `<line>`, `<polyline>`, `<polygon>`, `<use>`, `<symbol>`, `<text>` are skipped.
- No `viewBox` / `preserveAspectRatio` mapping.
- No CSS inheritance from ancestor `<g style="fill:...">` — fills must be on the `<path>` itself or via class.
- Stroke-only paths (no fill) won't show in the spatial tab. Add `STBuffer(stroke_width / 2)` downstream if you want strokes.
- `@single_layer = 1` will fail rendering when the UnionAggregate result exceeds the spatial tab's vertex budget. Default `0` for complex SVGs.

## Credits

- [Alastair Aitchison](https://alastaira.wordpress.com/) — the original "draw the SQL Server logo in SSMS" series, the Y-negation trick.
- [Michael J. Swart](https://michaeljswart.com/) — colour-via-row-order tricks.
- [Daniel Hutmacher](https://sqlsunday.com/) — multi-shape spatial-tab compositions.
- [SQLDBA.org](https://www.sqldba.org/post/drawing-in-sql-server-using-ssms-a-technical-article) — the workflow this automates.

## License

[MIT](LICENSE).
