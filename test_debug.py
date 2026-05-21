import pyodbc, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print("Starting...", flush=True)

conn = pyodbc.connect(
    r'DRIVER={ODBC Driver 17 for SQL Server};SERVER=MSI\old2017;'
    r'DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;',
    timeout=30)
conn.autocommit = True
cur = conn.cursor()
print("Connected.", flush=True)

svg_path = r'C:\GitHub\SVGme\edit-button.svg'

# Test: can SQL Server read this file?
print("Testing OPENROWSET BULK...", flush=True)
try:
    cur.execute(
        "SELECT LEN(CAST(BulkColumn AS NVARCHAR(MAX))) "
        "FROM OPENROWSET(BULK N'" + svg_path + "', SINGLE_BLOB) AS b"
    )
    row = cur.fetchone()
    print(f"  File size (chars): {row[0]}", flush=True)
except Exception as e:
    print(f"  ERROR: {e}", flush=True)

# Test: can we parse it as XML?
print("Testing XML parse...", flush=True)
try:
    cur.execute(
        "DECLARE @xml XML; "
        "SELECT @xml = CAST(BulkColumn AS XML) "
        "FROM OPENROWSET(BULK N'" + svg_path + "', SINGLE_BLOB) AS b; "
        "SELECT @xml.value("
        "'declare default element namespace \"http://www.w3.org/2000/svg\";"
        " count(//path)', 'INT') AS path_count"
    )
    row = cur.fetchone()
    print(f"  Path elements: {row[0]}", flush=True)
except Exception as e:
    print(f"  ERROR: {e}", flush=True)

# Test: extract one path's d attribute
print("Testing path extraction...", flush=True)
try:
    cur.execute(
        "DECLARE @xml XML; "
        "SELECT @xml = CAST(BulkColumn AS XML) "
        "FROM OPENROWSET(BULK N'" + svg_path + "', SINGLE_BLOB) AS b; "
        "SELECT p.value('@d', 'NVARCHAR(MAX)') AS d_attr "
        "FROM @xml.nodes("
        "'declare default element namespace \"http://www.w3.org/2000/svg\"; //path'"
        ") AS x(p)"
    )
    rows = cur.fetchall()
    for r in rows:
        d = r[0][:80] if r[0] else '(null)'
        print(f"  d: {d}", flush=True)
except Exception as e:
    print(f"  ERROR: {e}", flush=True)

# Test: full pipeline for one file
print("Testing full pipeline...", flush=True)
try:
    cur.execute(
        "DECLARE @xml XML; "
        "SELECT @xml = CAST(BulkColumn AS XML) "
        "FROM OPENROWSET(BULK N'" + svg_path + "', SINGLE_BLOB) AS b; "
        "IF OBJECT_ID('tempdb..#paths') IS NOT NULL DROP TABLE #paths; "
        ";WITH paths_raw AS ("
        "  SELECT ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS layer_id, "
        "    p.value('@d','NVARCHAR(MAX)') AS d_attr "
        "  FROM @xml.nodes("
        "    'declare default element namespace \"http://www.w3.org/2000/svg\"; //path'"
        "  ) AS x(p)) "
        "SELECT layer_id, d_attr INTO #paths FROM paths_raw "
        "WHERE d_attr IS NOT NULL AND LTRIM(RTRIM(d_attr))<>''; "
        ";WITH parsed AS ("
        "  SELECT p.layer_id, pts.subpath_id, pts.point_order, pts.x, -pts.y AS y "
        "  FROM #paths p "
        "  CROSS APPLY dbo.fn_ParseSvgPath(p.d_attr, 12) pts), "
        "rings AS ("
        "  SELECT layer_id, subpath_id, "
        "    STRING_AGG(CAST(CAST(x AS DECIMAL(18,6)) AS VARCHAR(32))+' '+"
        "               CAST(CAST(y AS DECIMAL(18,6)) AS VARCHAR(32)),',') "
        "      WITHIN GROUP (ORDER BY point_order) AS rc, "
        "    COUNT(DISTINCT CAST(CAST(x AS DECIMAL(18,6)) AS VARCHAR(32))+','+"
        "                   CAST(CAST(y AS DECIMAL(18,6)) AS VARCHAR(32))) AS dp "
        "  FROM parsed GROUP BY layer_id, subpath_id "
        "  HAVING COUNT(DISTINCT CAST(CAST(x AS DECIMAL(18,6)) AS VARCHAR(32))+','+"
        "                        CAST(CAST(y AS DECIMAL(18,6)) AS VARCHAR(32)))>=3), "
        "wkt AS ("
        "  SELECT layer_id, "
        "    CASE WHEN COUNT(*)=1 THEN 'POLYGON(('+MAX(rc)+'))' "
        "    ELSE 'MULTIPOLYGON('+STRING_AGG('('+rc+')',',') "
        "      WITHIN GROUP (ORDER BY subpath_id)+')' END AS wkt "
        "  FROM rings GROUP BY layer_id) "
        "SELECT p.layer_id, "
        "  geometry::STGeomFromText(w.wkt,0).STAsText() AS geom "
        "FROM #paths p LEFT JOIN wkt w ON w.layer_id=p.layer_id "
        "ORDER BY p.layer_id"
    )
    rows = cur.fetchall()
    print(f"  Results: {len(rows)} rows", flush=True)
    for r in rows:
        geom = r[1][:100] + '...' if r[1] and len(r[1]) > 100 else r[1]
        print(f"    layer={r[0]} geom={geom or 'NULL'}", flush=True)
except Exception as e:
    print(f"  ERROR: {e}", flush=True)

print("Done.", flush=True)
