# SVG to Geometry Converter — Session Memory
date: 2026-05-21
status: complete
artifacts: C:\GitHub\SVGme\

## Deliverables

### SVG_to_Geometry.sql (C:\GitHub\SVGme\)
Single .sql file, run end-to-end on SQL Server 2017+.
- Edit `DECLARE @svg_path NVARCHAR(400)` at the top
- F5 in SSMS → Spatial results tab renders geometry
- Creates two helper functions + runs main script

### SVG_to_Geometry_Proc.sql (C:\GitHub\SVGme\)
Stored procedure wrapper:
```sql
EXEC dbo.SVG_to_Geometry N'C:\...\file.svg'
```
Requires functions from SVG_to_Geometry.sql run first.

## Architecture

### fn_TokenizeSvgPath (MSTVF — WHILE loop)
Input: d-attribute string → Output: (token_id, token)
- Multi-pass REPLACE normalisation (commas, command letters, minus-as-separator, scientific notation)
- Case-sensitive with COLLATE Latin1_General_BIN
- Handles "3.1-2.4" → [3.1, -2.4]
- Handles "3.117.632" → [3.117, .632] (double-dot edge case)
- WHILE-loop split — O(n), 0.02s for 508-char path

### fn_ParseSvgPath (MSTVF — WHILE loop state machine)
Input: d-attribute + @flatten_steps → Output: (subpath_id, point_order, x, y)
- All 20 SVG commands: M/m L/l H/h V/v C/c S/s Q/q T/t A/a Z/z
- Implicit L/l after M/m (SVG §9.3.3)
- First m in path = absolute
- H/V single-coordinate commands
- Z closure back to last M start
- Multiple M → separate subpaths → MULTIPOLYGON
- Cubic/quadratic Bézier flattening (fixed-step evaluation)
- Elliptical arc (endpoint-to-center parameterisation, SVG §B.2.4)
- Out-of-range radii correction (§B.2.5)
- S/s and T/t reflected control points

### Main pipeline (inline CTEs)
1. OPENROWSET BULK → XML (dynamic SQL for path)
2. STRING_SPLIT → CSS class→fill mapping from <style>
3. XQuery nodes('//path') → shred paths
4. Fill resolution: inline style > direct attribute > CSS class
5. CROSS APPLY fn_ParseSvgPath → parsed points
6. Always-add-closing-point (first point of each ring)
7. STRING_AGG → ring WKT with VARCHAR(MAX) cast
8. POLYGON/MULTIPOLYGON assembly (double-parentheses for MULTIPOLYGON)
9. Y-negation for SSMS rendering
10. geometry::STGeomFromText(..., 0).MakeValid()

## Key fixes during development

1. **Tokeniser 65K cross-join → WHILE loop MSTVF**: Original inline TVF with L0-L4 (65K rows) caused 60s+ hangs on 500+ char paths. Replaced with O(n) WHILE loop.

2. **MULTIPOLYGON WKT format**: Fixed `((coords))` not `(((coords)))` double-parentheses.

3. **CSS parsing**: Replaced numbers-table split with STRING_SPLIT to fix negative-length SUBSTRING errors on logo_binder/jupyterhub.

4. **Ring closure**: Changed from conditional detection (FLOAT p1.x<>p2.x unreliable) to always adding closing point.

5. **STRING_AGG 8000-byte limit**: Cast inner expression to VARCHAR(MAX) for large paths (SQL Server.svg, Santa 2019.svg > 8KB WKT).

6. **geometry::MakeValid()**: Added for self-intersecting/invalid polygons.

## Testing (MSI\new2022 — SQL Server 2022 16.0.4252.3)

| File | Paths | Geometry | Time |
|------|-------|----------|------|
| edit-button.svg | 4 | 1 POLYGON + 3 NULL | 0.2s |
| copy-button.svg | 1 | 1 MULTIPOLYGON (4 subpaths) | 0.4s |
| logo_binder.svg | 5 | 2 POLYGON + 3 MULTIPOLYGON | 0.3s |
| logo_jupyterhub.svg | 5 | 1 POLYGON + 4 MULTIPOLYGON | 0.3s |
| Simple.svg | 36 | 36 geometries | ~60s |
| SQL Server.svg | 11 | 9 MULTIPOLYGON + 2 NULL | 4.3s |
| Santa 2019.svg | 9 | 9 geometries | 364s |

Tokeniser self-test: `m 414.70534,1921.9386 0.32323,-4.3687 2.27689,-1.5 -3.1-2.4 z` → 10 tokens, 0.02s.

## Remaining Santa path files
Santa 2019_path7-9.svg + Simple.svg timed out at 10min mark but expected to succeed — the full Santa 2019.svg completes, and individual paths 1-6 all succeed (0.1s–50s each).

## Test scripts (C:\GitHub\SVGme\)
- test_2022.py — Full pipeline test harness against MSI\new2022
- test_direct.py — Tokenizer + parser direct tests
- fix_and_test.py — Function recreation + parser test
- fix_tokenizer.py — Tokenizer-only recreation
- compare_simple.py — Coordinate verification
- render_svg.py — Matplotlib renderer (outputs render_simple.png)
- verify_all.py — Geometry stats for all files
