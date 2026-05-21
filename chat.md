Prompt:
I need you to build a pure T-SQL solution that reads an SVG file from disk and converts each <path> element into a SQL Server geometry polygon, ready to render in the SSMS spatial results tab. No CLR, no PowerShell, no external tools — T-SQL only, targeting SQL Server 2019 or later.
Input assumptions:

The SVG has already been cleaned in Inkscape: curves converted to lines, one top-level <g> group, paths use only M, L, m, l, H, V, h, v, Z, z commands.
Each <path> has a style attribute containing fill:#RRGGBB and a d attribute with the path data.
The file lives at a local path I'll provide as a variable.

Build it in these stages, and show me the code for each before moving to the next:

File read. Use OPENROWSET BULK ... SINGLE_BLOB to load the SVG into an XML variable. Include the SVG namespace declaration so XQuery works.
Path extraction. Shred the XML with .nodes('//path') into a temp table #paths with columns: layer_id (int identity), path_id (varchar), fill_hex (char(6), extracted from the style attribute), d_attr (varchar(max)).
Path parser. Write a function dbo.ParseSvgPath(@layer_id int, @d varchar(max)) that returns a table (point_order int, x float, y float) with all points converted to absolute coordinates. It must correctly handle:

Uppercase commands (absolute) vs lowercase (relative)
The SVG rule that coordinate pairs following an M/m are treated as implicit L/l commands
H/V (only one coordinate; the other is carried from the current point)
Z closing the subpath back to the last M start
Multiple M commands inside one d (treat each as a new layer or sub-polygon — your call, but document it)
Numbers separated by commas, spaces, or signs (- can act as a separator: 3.2-4.1 is two numbers)


WKT assembly and geometry creation. Wrap WKT generation in an inline TVF dbo.PolyFromCoords(@coords nvarchar(max)) so the caller never touches WKT strings. Flip the Y axis (negate y) so the image renders upright in SSMS. Ensure each polygon's first and last point match (close the ring if needed).
Final query. Produce one result set: layer_id, fill_hex, geom. This is what gets rendered.

Constraints and gotchas to respect:

No xp_cmdshell, no CLR, no SQLCLR-enabled functions, no Python/R via sp_execute_external_script.
The parser is the hard bit — don't skip the tokenisation edge cases. Test it against this string and show me the parsed output:
m 414.70534,1921.9386 0.32323,-4.3687 2.27689,-1.5 -3.1-2.4 z
Use STRING_SPLIT(..., ' ', 1) (SQL 2022) if available; otherwise a numbers table. Tell me which path you took.
Comment the parser heavily — I'll be reading and adapting it.

Deliverable: A single .sql file I can run end-to-end. At the top, a DECLARE @svg_path nvarchar(400) = N'C:\...' I can edit. At the bottom, the final SELECT that returns geometries to the spatial tab.
Before writing code, tell me anything ambiguous about the spec and I'll clarify. Don't guess — ask.

A few things worth knowing about why this prompt is shaped the way it is:
The "show me each stage before moving on" instruction matters. Without it, models tend to dump 400 lines at once where the parser silently mishandles relative coordinates and you don't notice until rendering. Stage gates let you catch that on stage 3.
The test string at the end is the cheapest insurance against a broken parser. 3.1-2.4 being two numbers (not subtraction) is the bug almost every first-pass SVG parser has. If the model's output handles that token correctly, the rest is probably fine.
Telling it to ask before guessing flips the default behaviour. Most models will happily invent specifications; explicit permission to ask back usually surfaces 2–3 real ambiguities (multi-M handling, SRID choice, how to deal with malformed input) that are better resolved up front than patched after.
If you want, paste the response back here and I'll review it before you run it.

Work in the folder C:\GitHub\SVGme.
The user wants me to build a T-SQL solution for parsing SVG files. Before writing code, they explicitly asked me to identify ambiguities and ask questions rather than guess. Let me analyze the spec carefully.

Key ambiguities I need to clarify:

Multi-M handling: The spec says "Multiple M commands inside one d (treat each as a new layer or sub-polygon — your call, but document it)." This is explicitly left open. I should ask how they want this handled - separate geometry objects or one multi-polygon?
SRID: The spec doesn't mention which SRID to use for the geometry. 0 (flat) or a specific one?
SQL Server version compatibility: The user mentions SQL Server 2019+, but STRING_SPLIT with the ordinal parameter requires 2022. I need to clarify whether they're on 2022 or if I should use an alternative approach for 2019.
Y-axis negation: The spec says "negate y" but doesn't specify whether to also apply an offset to position the SVG correctly.
Coordinate parsing: I'm looking at the test string to understand how the SVG path coordinates should be tokenized and parsed.
Now I'm identifying the key ambiguities I need to clarify before implementing. There's the question of whether multiple M commands should create separate geometry objects or be merged, which SRID to use, and whether to apply an offset to keep coordinates positive after negation. I also need to confirm whether we're targeting SQL Server 2019 or 2022, since that affects whether I can use the ordinal parameter in STRING_SPLIT.

Before writing any code, here are the ambiguities I need resolved:

1. Multi-M handling within a single d attribute SVG spec says subsequent M commands start new subpaths. Options:

Option A: Each M creates a separate row in the output (separate geometry). Simplest, matches "one polygon per subpath."
Option B: Collect all subpaths into a single MULTIPOLYGON geometry. More correct but harder to debug.
Option C: Each M gets a suffix on layer_id (e.g., 3.1, 3.2). Still separate rows but traceable back to the same path element.
2. SRID geometry::STGeomFromText() needs an SRID. 0 is flat/planar (fine for rendering in SSMS spatial tab), or do you want 4326 / something else? I'd default to 0.

3. SQL Server version — STRING_SPLIT ordinal You said 2019+. The third argument to STRING_SPLIT (ordinal) requires SQL Server 2022 (16.x) or Azure SQL. On 2019, I'd need a numbers-table approach or a WHILE loop tokenizer. Which engine version is the actual target? If it might run on 2019, I'll build the numbers-table path and note the 2022 alternative.

4. Coordinate space / bounding box Negating Y flips the image vertically so it renders "right-side up" in SSMS, but the raw SVG coordinates (e.g., x in 0–2000, y in 0–2000) will sit at large positive/negative values. SSMS auto-zooms, so this is cosmetic — but do you also want me to normalize/offset coordinates to a positive quadrant (e.g., min-x=0, min-y=0), or just negate and leave the raw values?

5. Malformed / empty d attributes If a <path> has an empty or missing d, should I skip it silently, produce a NULL geometry, or raise an error?

6. Test string expected output For your test string m 414.70534,1921.9386 0.32323,-4.3687 2.27689,-1.5 -3.1-2.4 z — the points in absolute coordinates would be:

point_order	x	y
1	414.70534	1921.9386
2	415.02857	1917.5699
3	417.30546	1916.0699
4	414.20546	1913.6699
(M point is absolute, then three relative pairs, then Z closes back to point 1.) Does that match your expectation, or am I off on the implicit-L rule you want?

Clarify these six and I'll build stage by stage, test string validated at each step.