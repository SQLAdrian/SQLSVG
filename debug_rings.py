import pyodbc, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = pyodbc.connect(
    r'DRIVER={ODBC Driver 17 for SQL Server};SERVER=MSI\new2022;'
    r'DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;',
    timeout=30)
conn.autocommit = True
cur = conn.cursor()

# Get the d_attr
cur.execute(
    "DECLARE @xml XML; "
    "SELECT @xml = CAST(BulkColumn AS XML) "
    "FROM OPENROWSET(BULK N'C:\\GitHub\\SVGme\\copy-button.svg', SINGLE_BLOB) AS b; "
    "SELECT p.value('@d','NVARCHAR(MAX)') "
    "FROM @xml.nodes("
    "'declare default element namespace \"http://www.w3.org/2000/svg\"; //path'"
    ") AS x(p)"
)
d_attr = cur.fetchone()[0]

print("=== First and last points per subpath ===", flush=True)
cur.execute(
    "SELECT subpath_id, "
    "  MIN(point_order) AS first_po, MAX(point_order) AS last_po "
    "FROM dbo.fn_ParseSvgPath(?, 8) "
    "GROUP BY subpath_id ORDER BY subpath_id",
    d_attr
)
for r in cur.fetchall():
    print(f"  subpath={r[0]}  first_po={r[1]}  last_po={r[2]}", flush=True)

print("\n=== First and last points (x,y) per subpath ===", flush=True)
cur.execute(
    ";WITH pts AS ("
    "  SELECT subpath_id, point_order, x, y "
    "  FROM dbo.fn_ParseSvgPath(?, 8)"
    "), "
    "bounds AS ("
    "  SELECT subpath_id, MIN(point_order) AS fp, MAX(point_order) AS lp "
    "  FROM pts GROUP BY subpath_id"
    ") "
    "SELECT b.subpath_id, "
    "  p1.point_order AS first_po, p1.x AS first_x, p1.y AS first_y, "
    "  p2.point_order AS last_po, p2.x AS last_x, p2.y AS last_y, "
    "  CASE WHEN p1.x <> p2.x OR p1.y <> p2.y THEN 'NEEDS CLOSE' ELSE 'OK' END AS status "
    "FROM bounds b "
    "JOIN pts p1 ON p1.subpath_id=b.subpath_id AND p1.point_order=b.fp "
    "JOIN pts p2 ON p2.subpath_id=b.subpath_id AND p2.point_order=b.lp "
    "ORDER BY b.subpath_id",
    d_attr
)
for r in cur.fetchall():
    print(f"  sub={r[0]} first=({r[2]}, {r[3]}) last=({r[5]}, {r[6]}) status={r[7]}", flush=True)

print("\nDone.", flush=True)
