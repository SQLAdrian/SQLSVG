import pyodbc, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
conn = pyodbc.connect(
    r'DRIVER={ODBC Driver 17 for SQL Server};SERVER=MSI\new2022;'
    r'DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;',
    timeout=60)
conn.autocommit = True
cur = conn.cursor()

svg = r'C:\GitHub\SVGme\Test\Simple.svg'

# Get first path d_attr + parse its first 10 absolute points
cur.execute(
    "DECLARE @xml XML, @d NVARCHAR(MAX); "
    "SELECT @xml = CAST(BulkColumn AS XML) "
    "FROM OPENROWSET(BULK N'" + svg + "', SINGLE_BLOB) AS b; "
    "SELECT TOP 1 @d = p.value('@d','NVARCHAR(MAX)') "
    "FROM @xml.nodes('declare default element namespace \"http://www.w3.org/2000/svg\"; //path') AS x(p); "
    "SELECT TOP 10 point_order, x, y FROM dbo.fn_ParseSvgPath(@d, 4) ORDER BY point_order"
)
print("First 10 points of path 1 (parsed absolute coordinates):")
for r in cur.fetchall():
    print(f"  po={r[0]:3d}  x={r[1]:12.4f}  y={r[2]:12.4f}")

# The SVG's first path starts with:
# m -292.12358,314.186
# After flatting with 4 steps, the first M point is absolute (-292.12358, 314.186)
# Then implicit l to next coords, then curve points

print(f"\nExpected first point: m -292.12358,314.186 (abs: -292.12358, 314.186)")
print(f"Note: Y should be NEGATED in the output geometry (-314.186)")
