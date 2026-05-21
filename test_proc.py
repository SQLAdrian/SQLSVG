import pyodbc, sys, time, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = pyodbc.connect(
    r'DRIVER={ODBC Driver 17 for SQL Server};SERVER=MSI\new2022;'
    r'DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;',
    timeout=30)
conn.autocommit = True
cur = conn.cursor()

# Drop old procedure
cur.execute("IF OBJECT_ID('dbo.SVG_to_Geometry') IS NOT NULL DROP PROCEDURE dbo.SVG_to_Geometry")
print("Dropped old proc.", flush=True)

# Create new procedure from file
with open(r'C:\GitHub\SVGme\SVG_to_Geometry_Proc.sql', 'r') as f:
    sql = f.read()
# Split on GO
batches = []
current = []
for line in sql.splitlines():
    if re.match(r'^\s*GO\s*$', line, re.IGNORECASE):
        if current:
            batches.append('\n'.join(current))
            current = []
    else:
        current.append(line)
if current:
    batches.append('\n'.join(current))
for i, b in enumerate(batches):
    if b.strip():
        cur.execute(b)
print("Created proc.", flush=True)

# Test it
# The procedure returns geometry type (works in SSMS spatial tab).
# pyodbc can't read geometry natively, so we insert into a temp table
# and select with .STAsText() to get the WKT string.

cur.execute(
    "CREATE TABLE #tmp (layer_id INT, fill_hex VARCHAR(10), geom geometry); "
    "INSERT #tmp EXEC dbo.SVG_to_Geometry N'C:\\GitHub\\SVGme\\edit-button.svg'; "
    "SELECT layer_id, fill_hex, geom.STAsText() AS geom FROM #tmp ORDER BY layer_id"
)
rows = cur.fetchall()
for r in rows:
    g = r[2]
    if g and len(g) > 120:
        g = g[:120] + '...'
    print(f"  layer={r[0]:3d}  fill=#{r[1] or 'none':8s}  geom={g or 'NULL'}", flush=True)

print("\nTest: EXEC dbo.SVG_to_Geometry N'C:\\GitHub\\SVGme\\Test\\SQL Server.svg'", flush=True)
t0 = time.time()
cur.execute(
    "CREATE TABLE #tmp (layer_id INT, fill_hex VARCHAR(10), geom geometry); "
    "INSERT #tmp EXEC dbo.SVG_to_Geometry N'C:\\GitHub\\SVGme\\Test\\SQL Server.svg'; "
    "SELECT layer_id, fill_hex, geom.STAsText() AS geom FROM #tmp ORDER BY layer_id"
)
rows = cur.fetchall()
print(f"  {len(rows)} rows in {time.time()-t0:.1f}s", flush=True)

print("\nDone.", flush=True)
