import pyodbc, sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = pyodbc.connect(
    r'DRIVER={ODBC Driver 17 for SQL Server};SERVER=MSI\new2022;'
    r'DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;',
    timeout=60)
conn.autocommit = True
cur = conn.cursor()

svg_files = [
    r'C:\GitHub\SVGme\edit-button.svg',
    r'C:\GitHub\SVGme\copy-button.svg',
    r'C:\GitHub\SVGme\logo_binder.svg',
    r'C:\GitHub\SVGme\logo_jupyterhub.svg',
    r'C:\GitHub\SVGme\Test\Simple.svg',
    r'C:\GitHub\SVGme\Test\SQL Server.svg',
    r'C:\GitHub\SVGme\Test\Santa 2019.svg',
]

for svg in svg_files:
    fname = os.path.basename(svg)
    
    # Count paths
    cur.execute(
        "DECLARE @xml XML; "
        "SELECT @xml = CAST(BulkColumn AS XML) "
        "FROM OPENROWSET(BULK N'" + svg + "', SINGLE_BLOB) AS b; "
        "SELECT @xml.value('declare default element namespace \"http://www.w3.org/2000/svg\"; "
        "  count(//path)', 'INT')"
    )
    path_count = cur.fetchone()[0]
    
    # Get geometry results via temp table (split across calls)
    cur.execute("IF OBJECT_ID('tempdb..#tmp') IS NOT NULL DROP TABLE #tmp; "
                "CREATE TABLE #tmp (layer_id INT, fill_hex VARCHAR(10), geom geometry)")
    try:
        cur.execute("INSERT #tmp EXEC dbo.SVG_to_Geometry N'" + svg + "'")
    except Exception as e:
        pass  # geometry type not supported by pyodbc, but data is inserted
    cur.execute(
        "SELECT COUNT(*), "
        "  COUNT(DISTINCT layer_id), "
        "  SUM(geom.STNumPoints()), "
        "  MIN(geom.STNumPoints()), MAX(geom.STNumPoints()), "
        "  SUM(geom.STNumGeometries()) "
        "FROM #tmp"
    )
    stats = cur.fetchone()
    
    # Also check for fill extraction
    cur.execute(
        "DECLARE @xml XML; "
        "SELECT @xml = CAST(BulkColumn AS XML) "
        "FROM OPENROWSET(BULK N'" + svg + "', SINGLE_BLOB) AS b; "
        "SELECT p.value('@fill','VARCHAR(200)'), "
        "  p.value('@style','NVARCHAR(MAX)'), "
        "  p.value('@class','VARCHAR(200)') "
        "FROM @xml.nodes('declare default element namespace \"http://www.w3.org/2000/svg\"; //path') AS x(p)"
    )
    fills_found = 0
    for r in cur.fetchall():
        if (r[0] and r[0] != 'none') or (r[1] and 'fill:' in r[1] and 'fill:none' not in r[1]) or r[2]:
            fills_found += 1
    
    print(f"{fname:30s}  SVG paths={path_count:3d}  "
          f"geom rows={stats[0]:3d}  total pts={stats[2]:6d}  "
          f"point range=[{stats[3]},{stats[4]}]  "
          f"sub-geoms={stats[5]:3d}  fills={fills_found}")
