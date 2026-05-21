import pyodbc, sys, time, os, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SERVER = r'MSI\new2022'
SVG_DIR = r'C:\GitHub\SVGme\Test'
SQL_FILE = r'C:\GitHub\SVGme\SVG_to_Geometry.sql'
conn = pyodbc.connect(
    f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SERVER};'
    f'DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;',
    timeout=30)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT @@VERSION")
print(f"Connected: {cur.fetchone()[0].split(chr(10))[0]}", flush=True)

# Create functions from the SQL file
sql_file = SQL_FILE
with open(sql_file, 'r', encoding='utf-8') as f:
    sql = f.read()

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

func_batches = []
main_batches = []
found_main = False
for b in batches:
    if not found_main and re.search(r'DECLARE\s+@svg_path', b, re.IGNORECASE):
        found_main = True
    if found_main:
        main_batches.append(b)
    else:
        func_batches.append(b)

print(f"Creating {len(func_batches)} function batches...", flush=True)
for i, b in enumerate(func_batches):
    try:
        cur.execute(b)
    except Exception as e:
        err = str(e).split('\n')[0][:120]
        print(f"  Batch {i}: {err}", flush=True)
print("Functions created.", flush=True)

# Test tokenizer
print("\n=== Tokenizer test ===", flush=True)
cur.execute(
    "SELECT token_id, token FROM dbo.fn_TokenizeSvgPath("
    "'m 414.70534,1921.9386 0.32323,-4.3687 2.27689,-1.5 -3.1-2.4 z'"
    ") ORDER BY token_id"
)
for r in cur.fetchall():
    print(f"  [{r[0]:2d}] {r[1]}", flush=True)

# Test each SVG file
svg_files = sorted([f for f in os.listdir(SVG_DIR) if f.endswith('.svg')])

# Full pipeline SQL (uses STRING_SPLIT for CSS)
PIPE_SQL = """
DECLARE @xml XML;
SELECT @xml = CAST(BulkColumn AS XML)
FROM OPENROWSET(BULK N'{path}', SINGLE_BLOB) AS b;

IF OBJECT_ID('tempdb..#paths') IS NOT NULL DROP TABLE #paths;

;WITH
style_raw AS (
    SELECT @xml.value(
        'declare default element namespace "http://www.w3.org/2000/svg";
         (//style/text())[1]', 'NVARCHAR(MAX)') AS txt
),
css_rules AS (
    SELECT LTRIM(RTRIM(value)) AS rule_frag
    FROM style_raw sr
    CROSS APPLY STRING_SPLIT(
        REPLACE(REPLACE(ISNULL(sr.txt,''), CHAR(13),''), CHAR(10),''), '}')
    WHERE LTRIM(RTRIM(value)) LIKE '.%{%'
),
css_parsed AS (
    SELECT
        LTRIM(RTRIM(SUBSTRING(cr.rule_frag,
            CHARINDEX('.',cr.rule_frag)+1,
            CHARINDEX('{',cr.rule_frag)-CHARINDEX('.',cr.rule_frag)-1
        ))) AS class_name,
        CASE WHEN CHARINDEX('fill:',cr.rule_frag)>0
        THEN LTRIM(RTRIM(SUBSTRING(cr.rule_frag,
            CHARINDEX('fill:',cr.rule_frag)+5,
            CASE WHEN CHARINDEX(';',cr.rule_frag,CHARINDEX('fill:',cr.rule_frag))>0
                 THEN CHARINDEX(';',cr.rule_frag,CHARINDEX('fill:',cr.rule_frag))
                 ELSE LEN(cr.rule_frag)+1 END
            -CHARINDEX('fill:',cr.rule_frag)-5)))
        ELSE NULL END AS fill_raw
    FROM css_rules cr
    WHERE cr.rule_frag LIKE '.%{%'
),
css_fills AS (
    SELECT class_name,
        CASE WHEN fill_raw IN ('none','transparent','inherit','initial') THEN NULL
             WHEN fill_raw LIKE '#[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]' AND LEN(fill_raw)=4
             THEN SUBSTRING(fill_raw,2,1)+SUBSTRING(fill_raw,2,1)
                 +SUBSTRING(fill_raw,3,1)+SUBSTRING(fill_raw,3,1)
                 +SUBSTRING(fill_raw,4,1)+SUBSTRING(fill_raw,4,1)
             WHEN fill_raw LIKE '#%' THEN SUBSTRING(fill_raw,2,6)
             ELSE NULL END AS fill_hex
    FROM css_parsed WHERE fill_raw IS NOT NULL
),
paths_raw AS (
    SELECT ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS layer_id,
        p.value('@id','VARCHAR(200)') AS path_id,
        p.value('@style','NVARCHAR(MAX)') AS style_attr,
        p.value('@fill','VARCHAR(200)') AS fill_attr,
        p.value('@class','VARCHAR(200)') AS class_attr,
        p.value('@d','NVARCHAR(MAX)') AS d_attr
    FROM @xml.nodes(
        'declare default element namespace "http://www.w3.org/2000/svg"; //path'
    ) AS x(p)
),
paths AS (
    SELECT pr.layer_id, pr.path_id, pr.d_attr,
        CASE WHEN pr.style_attr LIKE '%fill:%' THEN
            CASE WHEN SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+5,4)
                      LIKE '#[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]'
                 THEN SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+6,1)
                     +SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+6,1)
                     +SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+7,1)
                     +SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+7,1)
                     +SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+8,1)
                     +SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+8,1)
                 WHEN SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+5,7)
                      LIKE '#[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]'
                 THEN SUBSTRING(pr.style_attr,CHARINDEX('fill:',pr.style_attr)+6,6)
                 ELSE NULL END
        WHEN pr.fill_attr IS NOT NULL AND pr.fill_attr NOT IN ('none','transparent') THEN
            CASE WHEN pr.fill_attr LIKE '#[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]' AND LEN(pr.fill_attr)=4
                 THEN SUBSTRING(pr.fill_attr,2,1)+SUBSTRING(pr.fill_attr,2,1)
                     +SUBSTRING(pr.fill_attr,3,1)+SUBSTRING(pr.fill_attr,3,1)
                     +SUBSTRING(pr.fill_attr,4,1)+SUBSTRING(pr.fill_attr,4,1)
                 WHEN pr.fill_attr LIKE '#%' THEN SUBSTRING(pr.fill_attr,2,6)
                 ELSE NULL END
        WHEN pr.class_attr IS NOT NULL THEN cf.fill_hex
        ELSE NULL END AS fill_hex
    FROM paths_raw pr
    LEFT JOIN css_fills cf ON cf.class_name = pr.class_attr
)
SELECT layer_id, path_id, fill_hex, d_attr
INTO #paths FROM paths
WHERE d_attr IS NOT NULL AND LTRIM(RTRIM(d_attr)) <> '';

;WITH parsed AS (
    SELECT p.layer_id, pts.subpath_id, pts.point_order, pts.x, -pts.y AS y
    FROM #paths p
    CROSS APPLY dbo.fn_ParseSvgPath(p.d_attr, 12) pts
),
ring_ends AS (
    SELECT layer_id, subpath_id, MIN(point_order) AS fp, MAX(point_order) AS lp
    FROM parsed GROUP BY layer_id, subpath_id
),
closing_pts AS (
    SELECT re.layer_id, re.subpath_id, 999999 AS point_order, p.x, p.y
    FROM ring_ends re
    JOIN parsed p ON p.layer_id=re.layer_id AND p.subpath_id=re.subpath_id AND p.point_order=re.fp
),
all_pts AS (
    SELECT * FROM parsed UNION ALL SELECT * FROM closing_pts
),
rings AS (
    SELECT layer_id, subpath_id,
        STRING_AGG(
            CAST(CAST(CAST(x AS DECIMAL(18,6)) AS VARCHAR(32))+' '+
                 CAST(CAST(y AS DECIMAL(18,6)) AS VARCHAR(32))
                 AS VARCHAR(MAX)),',')
          WITHIN GROUP (ORDER BY point_order) AS rc
    FROM all_pts GROUP BY layer_id, subpath_id
    HAVING COUNT(DISTINCT CAST(CAST(x AS DECIMAL(18,6)) AS VARCHAR(32))+','+
                          CAST(CAST(y AS DECIMAL(18,6)) AS VARCHAR(32)))>=3
),
wkt AS (
    SELECT layer_id,
        CASE WHEN COUNT(*)=1 THEN 'POLYGON(('+MAX(rc)+'))'
        ELSE 'MULTIPOLYGON('+STRING_AGG('(('+rc+'))',',')
            WITHIN GROUP (ORDER BY subpath_id)+')' END AS wkt
    FROM rings GROUP BY layer_id
)
SELECT p.layer_id, p.fill_hex,
    geometry::STGeomFromText(w.wkt,0).MakeValid().STAsText() AS geom
FROM #paths p LEFT JOIN wkt w ON w.layer_id=p.layer_id
ORDER BY p.layer_id
"""

for svg_file in svg_files:
    svg_path = os.path.join(SVG_DIR, svg_file)
    print(f"\n=== {svg_file} ===", flush=True)
    t0 = time.time()

    try:
        sql_extract = PIPE_SQL.split(';WITH parsed AS')[0].replace('{path}', svg_path.replace("'", "''"))
        sql_geom = ';WITH parsed AS' + PIPE_SQL.split(';WITH parsed AS')[1]

        cur.execute(sql_extract)
        cur.execute(sql_geom)
        rows = cur.fetchall()
        elapsed = time.time() - t0
        print(f"  Results ({len(rows)} rows) in {elapsed:.1f}s:", flush=True)
        for r in rows:
            g = r[2]
            if g and len(g) > 150:
                g = g[:150] + '...'
            print(f"    layer={r[0]:3d}  fill=#{r[1] or 'none':8s}  geom={g or 'NULL'}", flush=True)
    except Exception as e:
        err = str(e).split('\n')[:3]
        print(f"  ERROR after {time.time()-t0:.1f}s:", flush=True)
        for line in err:
            print(f"    {line}", flush=True)

print("\nDone.", flush=True)
