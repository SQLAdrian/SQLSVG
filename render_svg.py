import pyodbc, sys, re, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = pyodbc.connect(
    r'DRIVER={ODBC Driver 17 for SQL Server};SERVER=MSI\new2022;'
    r'DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;',
    timeout=120)
conn.autocommit = True
cur = conn.cursor()

svg_file = r'C:\GitHub\SVGme\Test\Simple.svg'

# Step 1: Load SVG as XML
cur.execute(
    "DECLARE @xml XML; "
    "SELECT @xml = CAST(BulkColumn AS XML) "
    "FROM OPENROWSET(BULK N'" + svg_file + "', SINGLE_BLOB) AS b; "
    "SELECT @xml"
)
xml = cur.fetchone()[0]

# Step 2: Get viewBox for coordinate normalization
cur.execute(
    "DECLARE @xml XML; "
    "SELECT @xml = CAST(BulkColumn AS XML) "
    "FROM OPENROWSET(BULK N'" + svg_file + "', SINGLE_BLOB) AS b; "
    "SELECT @xml.value('declare default element namespace \"http://www.w3.org/2000/svg\"; "
    "  (/svg[1]/@viewBox)[1]', 'VARCHAR(200)')"
)
viewbox = cur.fetchone()[0]
print(f"viewBox: {viewbox}")

# Step 3: Parse all paths and collect coordinates
cur.execute(
    "DECLARE @xml XML; "
    "SELECT @xml = CAST(BulkColumn AS XML) "
    "FROM OPENROWSET(BULK N'" + svg_file + "', SINGLE_BLOB) AS b; "
    "SELECT "
    "  ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS path_id, "
    "  COALESCE(p.value('@fill','VARCHAR(200)'), "
    "    SUBSTRING(p.value('@style','NVARCHAR(MAX)'), "
    "      CHARINDEX('fill:', p.value('@style','NVARCHAR(MAX)'))+5, 7)) AS fill_color, "
    "  p.value('@d','NVARCHAR(MAX)') AS d_attr "
    "FROM @xml.nodes('declare default element namespace \"http://www.w3.org/2000/svg\"; //path') AS x(p)"
)
paths = cur.fetchall()
print(f"Total paths: {len(paths)}")

# Step 4: For each path, parse with fn_ParseSvgPath and collect coordinates
all_polygons = []
for path_id, fill_color, d_attr in paths:
    if not d_attr or not d_attr.strip():
        continue
    cur.execute(
        "SELECT subpath_id, point_order, x, y "
        "FROM dbo.fn_ParseSvgPath(?, 8) ORDER BY subpath_id, point_order",
        d_attr
    )
    points = cur.fetchall()
    if not points:
        continue
    
    # Group by subpath
    subpaths = {}
    for sub_id, po, x, y in points:
        subpaths.setdefault(sub_id, []).append((x, y))
    
    for sub_id, coords in subpaths.items():
        if len(coords) >= 3:
            all_polygons.append({
                'fill': fill_color,
                'points': coords,
                'path_id': path_id,
                'sub_id': sub_id
            })

print(f"Polygons: {len(all_polygons)}")

# Step 5: Extract SVG container group transforms
# Get the top-level <g> transform
cur.execute(
    "DECLARE @xml XML; "
    "SELECT @xml = CAST(BulkColumn AS XML) "
    "FROM OPENROWSET(BULK N'" + svg_file + "', SINGLE_BLOB) AS b; "
    "SELECT @xml.value('declare default element namespace \"http://www.w3.org/2000/svg\"; "
    "  (//g[1]/@transform)[1]', 'VARCHAR(500)')"
)
transform = cur.fetchone()[0]
print(f"Top-level transform: {transform}")

# Step 6: Render with matplotlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import matplotlib.colors as mcolors

fig, ax = plt.subplots(1, 1, figsize=(14, 14))
ax.set_aspect('equal')
ax.set_facecolor('#ffffff')

for poly in all_polygons:
    coords = poly['points']
    fill = poly['fill'] or '#000000'
    # Parse hex color
    if fill and fill.startswith('#'):
        color = fill
    else:
        color = '#000000'
    
    # Negate Y for SSMS-style rendering (SVG has Y-down, plot has Y-up)
    # OR keep Y as-is for SVG-native rendering (Y-down)
    # We'll render both ways
    
    xy = [(x, y) for x, y in coords]
    p = Polygon(xy, closed=True, facecolor=color, edgecolor='#333333', 
                linewidth=0.3, alpha=0.7)
    ax.add_patch(p)

# Auto-fit
all_x = [p[0] for poly in all_polygons for p in poly['points']]
all_y = [p[1] for poly in all_polygons for p in poly['points']]
if all_x:
    margin = (max(all_x) - min(all_x)) * 0.05
    ax.set_xlim(min(all_x) - margin, max(all_x) + margin)
    ax.set_ylim(min(all_y) - margin, max(all_y) + margin)

ax.set_title(f"Simple.svg ({len(all_polygons)} polygons)\nSVG-native Y-down rendering")
plt.tight_layout()

output_path = r'C:\GitHub\SVGme\render_simple.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"\nSaved: {output_path}")
print(f"Image dims: {os.path.getsize(output_path)} bytes")
