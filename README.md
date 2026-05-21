# SQLSVG

Render any SVG inside SQL Server Management Studio's Spatial Results tab — pure T-SQL, no CLR, no PowerShell, no external converters. Drop an SVG path into the script, hit F5, look at the spatial tab.

Inspired by [Drawing in SQL Server using SSMS](https://www.sqldba.org/post/drawing-in-sql-server-using-ssms-a-technical-article) — that workflow was Inkscape + MyGeoData + manual WKT paste. This is the same idea, automated, end-to-end inside the database.

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
