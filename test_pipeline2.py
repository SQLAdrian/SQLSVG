import pyodbc, sys, os, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SVG_DIR = r'C:\GitHub\SVGme'
conn = pyodbc.connect(
    r'DRIVER={ODBC Driver 17 for SQL Server};SERVER=MSI\old2017;'
    r'DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;',
    timeout=60)
conn.autocommit = True
cur = conn.cursor()

svg_files = sorted([f for f in os.listdir(SVG_DIR) if f.endswith('.svg')])

for svg_file in svg_files:
    svg_path = os.path.join(SVG_DIR, svg_file)
    print(f'\n=== {svg_file} ===', flush=True)
    t0 = time.time()

    # Step 1: Load SVG + extract paths into #paths
    try:
        cur.execute(
            "IF OBJECT_ID('tempdb..#paths') IS NOT NULL DROP TABLE #paths"
        )
        cur.execute(
            "DECLARE @xml XML; "
            "SELECT @xml = CAST(BulkColumn AS XML) "
            "FROM OPENROWSET(BULK N'" + svg_path.replace("'","''") + "', SINGLE_BLOB) AS b; "
            "IF OBJECT_ID('tempdb..#paths') IS NOT NULL DROP TABLE #paths; "
            ";WITH "
            "L0 AS (SELECT 1 AS c UNION ALL SELECT 1), "
            "L1 AS (SELECT 1 AS c FROM L0 a CROSS JOIN L0 b), "
            "L2 AS (SELECT 1 AS c FROM L1 a CROSS JOIN L1 b), "
            "L3 AS (SELECT 1 AS c FROM L2 a CROSS JOIN L2 b), "
            "nums AS (SELECT ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS n FROM L3), "
            "style_raw AS ("
            "  SELECT @xml.value("
            "    'declare default element namespace \"http://www.w3.org/2000/svg\";"
            "     (//style/text())[1]', 'NVARCHAR(MAX)') AS txt), "
            "css_rules AS ("
            "  SELECT LTRIM(RTRIM(SUBSTRING("
            "    REPLACE(REPLACE(sr.txt, CHAR(13),''), CHAR(10),''), n, "
            "    ISNULL(NULLIF(CHARINDEX('}', REPLACE(REPLACE(sr.txt, CHAR(13),''), CHAR(10),''), n), 0), "
            "      LEN(REPLACE(REPLACE(sr.txt, CHAR(13),''), CHAR(10),''))+1) - n"
            "  ))) AS rule_frag "
            "  FROM style_raw sr CROSS JOIN nums "
            "  WHERE sr.txt IS NOT NULL "
            "    AND n BETWEEN 1 AND LEN(REPLACE(REPLACE(sr.txt, CHAR(13),''), CHAR(10),'')) "
            "    AND (n=1 OR SUBSTRING(REPLACE(REPLACE(sr.txt, CHAR(13),''), CHAR(10),''), n-1, 1)='}') "
            "    AND CHARINDEX('{', SUBSTRING(REPLACE(REPLACE(sr.txt, CHAR(13),''), CHAR(10),''), n, "
            "         LEN(REPLACE(REPLACE(sr.txt, CHAR(13),''), CHAR(10),'')))) > 0), "
            "css_parsed AS ("
            "  SELECT "
            "    LTRIM(RTRIM(SUBSTRING(cr.rule_frag, CHARINDEX('.',cr.rule_frag)+1, "
            "      CHARINDEX('{',cr.rule_frag)-CHARINDEX('.',cr.rule_frag)-1))) AS class_name, "
            "    LTRIM(RTRIM(SUBSTRING(cr.rule_frag, CHARINDEX('fill:',cr.rule_frag)+5, "
            "      CASE WHEN CHARINDEX(';',cr.rule_frag,CHARINDEX('fill:',cr.rule_frag))>0 "
            "           THEN CHARINDEX(';',cr.rule_frag,CHARINDEX('fill:',cr.rule_frag)) "
            "           ELSE LEN(cr.rule_frag)+1 END "
            "      -CHARINDEX('fill:',cr.rule_frag)-5))) AS fill_raw "
            "  FROM css_rules cr "
            "  WHERE cr.rule_frag LIKE '.%{%' AND CHARINDEX('fill:',cr.rule_frag)>0), "
            "css_fills AS ("
            "  SELECT class_name, "
            "    CASE WHEN fill_raw IN ('none','transparent','inherit','initial') THEN NULL "
            "         WHEN fill_raw LIKE '#[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]' AND LEN(fill_raw)=4 "
            "         THEN SUBSTRING(fill_raw,2,1)+SUBSTRING(fill_raw,2,1)"
            "             +SUBSTRING(fill_raw,3,1)+SUBSTRING(fill_raw,3,1)"
            "             +SUBSTRING(fill_raw,4,1)+SUBSTRING(fill_raw,4,1) "
            "         WHEN fill_raw LIKE '#%' THEN SUBSTRING(fill_raw,2,6) "
            "         ELSE NULL END AS fill_hex "
            "  FROM css_parsed), "
            "paths_raw AS ("
            "  SELECT ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS layer_id, "
            "    p.value('@id','VARCHAR(200)') AS path_id, "
            "    p.value('@style','NVARCHAR(MAX)') AS style_attr, "
            "    p.value('@fill','VARCHAR(200)') AS fill_attr, "
            "    p.value('@class','VARCHAR(200)') AS class_attr, "
            "    p.value('@d','NVARCHAR(MAX)') AS d_attr "
            "  FROM @xml.nodes("
            "    'declare default element namespace \"http://www.w3.org/2000/svg\"; //path'"
            "  ) AS x(p)), "
            "paths AS ("
            "  SELECT pr.layer_id, pr.path_id, pr.d_attr, "
            "    CASE WHEN pr.style_attr LIKE '%fill:%' THEN "
            "      CASE WHEN SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+5,4) "
            "                LIKE '#[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]' "
            "           THEN SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+6,1)"
            "               +SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+6,1)"
            "               +SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+7,1)"
            "               +SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+7,1)"
            "               +SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+8,1)"
            "               +SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+8,1) "
            "           WHEN SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+5,7) "
            "                LIKE '#[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]' "
            "           THEN SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+6,6) "
            "           ELSE NULL END "
            "    WHEN pr.fill_attr IS NOT NULL AND pr.fill_attr NOT IN ('none','transparent') THEN "
            "      CASE WHEN pr.fill_attr LIKE '#[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]' AND LEN(pr.fill_attr)=4 "
            "           THEN SUBSTRING(pr.fill_attr,2,1)+SUBSTRING(pr.fill_attr,2,1)"
            "               +SUBSTRING(pr.fill_attr,3,1)+SUBSTRING(pr.fill_attr,3,1)"
            "               +SUBSTRING(pr.fill_attr,4,1)+SUBSTRING(pr.fill_attr,4,1) "
            "           WHEN pr.fill_attr LIKE '#%' THEN SUBSTRING(pr.fill_attr,2,6) "
            "           ELSE NULL END "
            "    WHEN pr.class_attr IS NOT NULL THEN cf.fill_hex "
            "    ELSE NULL END AS fill_hex "
            "  FROM paths_raw pr "
            "  LEFT JOIN css_fills cf ON cf.class_name = pr.class_attr) "
            "SELECT layer_id, path_id, fill_hex, d_attr "
            "INTO #paths FROM paths "
            "WHERE d_attr IS NOT NULL AND LTRIM(RTRIM(d_attr)) <> ''"
        )
        # Count rows
        cur.execute("SELECT COUNT(*) FROM #paths")
        n = cur.fetchone()[0]
        print(f'  Extracted {n} paths', flush=True)
    except Exception as e:
        print(f'  EXTRACT ERROR: {e}', flush=True)
        continue

    # Step 2: Build geometry
    try:
        cur.execute(
            ";WITH parsed AS ("
            "  SELECT p.layer_id, pts.subpath_id, pts.point_order, pts.x, -pts.y AS y "
            "  FROM #paths p "
            "  CROSS APPLY dbo.fn_ParseSvgPath(p.d_attr, 12) pts), "
            "ring_ends AS ("
            "  SELECT layer_id, subpath_id, MIN(point_order) AS fp, MAX(point_order) AS lp "
            "  FROM parsed GROUP BY layer_id, subpath_id), "
            "unclosed AS ("
            "  SELECT re.layer_id, re.subpath_id FROM ring_ends re "
            "  JOIN parsed p1 ON p1.layer_id=re.layer_id AND p1.subpath_id=re.subpath_id AND p1.point_order=re.fp "
            "  JOIN parsed p2 ON p2.layer_id=re.layer_id AND p2.subpath_id=re.subpath_id AND p2.point_order=re.lp "
            "  WHERE p1.x<>p2.x OR p1.y<>p2.y), "
            "closing_pts AS ("
            "  SELECT uc.layer_id, uc.subpath_id, 999999 AS point_order, p.x, p.y "
            "  FROM unclosed uc "
            "  JOIN parsed p ON p.layer_id=uc.layer_id AND p.subpath_id=uc.subpath_id "
            "  AND p.point_order=(SELECT MIN(point_order) FROM parsed WHERE layer_id=uc.layer_id AND subpath_id=uc.subpath_id)), "
            "all_pts AS ("
            "  SELECT * FROM parsed UNION ALL SELECT * FROM closing_pts), "
            "rings AS ("
            "  SELECT layer_id, subpath_id, "
            "    STRING_AGG(CAST(CAST(x AS DECIMAL(18,6)) AS VARCHAR(32))+' '+"
            "               CAST(CAST(y AS DECIMAL(18,6)) AS VARCHAR(32)),',') "
            "      WITHIN GROUP (ORDER BY point_order) AS rc, "
            "    COUNT(DISTINCT CAST(CAST(x AS DECIMAL(18,6)) AS VARCHAR(32))+','+"
            "                   CAST(CAST(y AS DECIMAL(18,6)) AS VARCHAR(32))) AS dp "
            "  FROM all_pts GROUP BY layer_id, subpath_id "
            "  HAVING COUNT(DISTINCT CAST(CAST(x AS DECIMAL(18,6)) AS VARCHAR(32))+','+"
            "                        CAST(CAST(y AS DECIMAL(18,6)) AS VARCHAR(32)))>=3), "
            "wkt AS ("
            "  SELECT layer_id, "
            "    CASE WHEN COUNT(*)=1 THEN 'POLYGON(('+MAX(rc)+'))' "
            "    ELSE 'MULTIPOLYGON('+STRING_AGG('('+rc+')',',') "
            "      WITHIN GROUP (ORDER BY subpath_id)+')' END AS wkt "
            "  FROM rings GROUP BY layer_id) "
            "SELECT p.layer_id, p.fill_hex, "
            "  geometry::STGeomFromText(w.wkt,0).STAsText() AS geom "
            "FROM #paths p LEFT JOIN wkt w ON w.layer_id=p.layer_id "
            "ORDER BY p.layer_id"
        )
        rows = cur.fetchall()
        elapsed = time.time() - t0
        print(f'  Results ({len(rows)} rows) in {elapsed:.1f}s:', flush=True)
        for r in rows:
            g = r[2]
            if g and len(g) > 120:
                g = g[:120] + '...'
            print(f'    layer={r[0]:3d}  fill=#{r[1] or "none":8s}  geom={g or "NULL"}', flush=True)
    except Exception as e:
        print(f'  GEOM ERROR: {e}', flush=True)

print('\nDone.', flush=True)
