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
print(f"d_attr ({len(d_attr)} chars):", flush=True)
print(f"  {d_attr}", flush=True)

# Tokenize it
print(f"\n=== Tokenizing...", flush=True)
t0 = time.time()
cur.execute("SELECT token_id, token FROM dbo.fn_TokenizeSvgPath(?) ORDER BY token_id", d_attr)
tokens = cur.fetchall()
print(f"  {len(tokens)} tokens in {time.time()-t0:.2f}s", flush=True)
for t in tokens:
    print(f"  [{t[0]:3d}] {t[1]}", flush=True)

# Parse it (with short timeout via SQL)
print(f"\n=== Parsing...", flush=True)
t0 = time.time()
try:
    cur.execute(
        "SELECT subpath_id, point_order, x, y "
        "FROM dbo.fn_ParseSvgPath(?, 6) ORDER BY point_order",
        d_attr
    )
    rows = cur.fetchall()
    print(f"  {len(rows)} points in {time.time()-t0:.2f}s", flush=True)
    for r in rows[:20]:
        print(f"  sub={r[0]} po={r[1]:3d} x={r[2]:10.4f} y={r[3]:10.4f}", flush=True)
    if len(rows) > 20:
        print(f"  ... ({len(rows)-20} more)", flush=True)
except Exception as e:
    print(f"  ERROR after {time.time()-t0:.2f}s: {e}", flush=True)
