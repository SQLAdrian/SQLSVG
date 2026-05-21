import pyodbc, sys, time, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = pyodbc.connect(
    r'DRIVER={ODBC Driver 17 for SQL Server};SERVER=MSI\new2022;'
    r'DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;',
    timeout=30)
conn.autocommit = True
cur = conn.cursor()

# Recreate tokenizer from the SQL file
with open(r'C:\GitHub\SVGme\SVG_to_Geometry.sql', 'r') as f:
    sql = f.read()

lines = sql.splitlines()
capture = False
buf = []
for line in lines:
    if 'CREATE FUNCTION dbo.fn_TokenizeSvgPath' in line:
        capture = True
    if capture:
        buf.append(line)
    if capture and line.strip() == 'GO':
        break
tokenizer_sql = '\n'.join(buf)
if tokenizer_sql.endswith('GO'):
    tokenizer_sql = tokenizer_sql[:-2].strip()

cur.execute("IF OBJECT_ID('dbo.fn_TokenizeSvgPath') IS NOT NULL DROP FUNCTION dbo.fn_TokenizeSvgPath")
cur.execute(tokenizer_sql)
print("Tokeniser recreated.", flush=True)

# Test on copy-button.svg
print("\n=== copy-button.svg ===", flush=True)
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
print(f"  d_attr: {len(d_attr)} chars", flush=True)

# Tokenize
t0 = time.time()
cur.execute("SELECT token_id, token FROM dbo.fn_TokenizeSvgPath(?) ORDER BY token_id", d_attr)
tokens = cur.fetchall()
print(f"  {len(tokens)} tokens in {time.time()-t0:.2f}s", flush=True)
# Show the double-dot fix
for t in tokens:
    if '.' in t[1]:
        dots = t[1].count('.')
        if dots > 1:
            print(f"  [{t[0]:3d}] {t[1]}  <<< MULTI-DOT")
for t in tokens:
    print(f"  [{t[0]:3d}] {t[1]}")
    if t[0] > 15: break  # just first 15

# Parse
print(f"\n  Parsing...", flush=True)
t0 = time.time()
try:
    cur.execute(
        "SELECT subpath_id, point_order, x, y "
        "FROM dbo.fn_ParseSvgPath(?, 8) ORDER BY point_order",
        d_attr
    )
    rows = cur.fetchall()
    print(f"  {len(rows)} points in {time.time()-t0:.2f}s", flush=True)
    for r in rows[:10]:
        print(f"  sub={r[0]} po={r[1]:3d} x={r[2]:10.4f} y={r[3]:10.4f}", flush=True)
    if len(rows) > 10:
        print(f"  ... ({len(rows)-10} more)", flush=True)
except Exception as e:
    print(f"  PARSE ERROR: {e}", flush=True)

# Also test the parser function still exists
cur.execute("IF OBJECT_ID('dbo.fn_ParseSvgPath') IS NOT NULL PRINT 'Parser exists'")
print("Done.", flush=True)
