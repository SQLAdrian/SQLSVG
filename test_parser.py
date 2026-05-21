import pyodbc, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = pyodbc.connect(
    r'DRIVER={ODBC Driver 17 for SQL Server};SERVER=MSI\old2017;'
    r'DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;',
    timeout=30)
conn.autocommit = True
cur = conn.cursor()

# First get the full d-attr from copy-button.svg
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
print(f"d_attr length: {len(d_attr)}", flush=True)
print(f"d_attr: {d_attr[:100]}...", flush=True)

# Tokenize it first
print("\n=== Tokenizing...", flush=True)
t0 = time.time()
cur.execute(
    "SELECT token_id, token FROM dbo.fn_TokenizeSvgPath(?) ORDER BY token_id",
    d_attr
)
tokens = cur.fetchall()
print(f"  {len(tokens)} tokens in {time.time()-t0:.2f}s", flush=True)
for t in tokens[:20]:
    print(f"  [{t[0]:3d}] {t[1]}", flush=True)
if len(tokens) > 20:
    print(f"  ... ({len(tokens)-20} more)", flush=True)

# Parse it
print("\n=== Parsing...", flush=True)
t0 = time.time()
try:
    cur.execute(
        "SELECT subpath_id, point_order, x, y "
        "FROM dbo.fn_ParseSvgPath(?, 12) ORDER BY point_order",
        d_attr
    )
    rows = cur.fetchall()
    elapsed = time.time() - t0
    print(f"  {len(rows)} points in {elapsed:.2f}s", flush=True)
    for r in rows[:10]:
        print(f"  sub={r[0]} po={r[1]:3d} x={r[2]:10.4f} y={r[3]:10.4f}", flush=True)
    if len(rows) > 10:
        print(f"  ... ({len(rows)-10} more)", flush=True)
except Exception as e:
    print(f"  ERROR: {e}", flush=True)

print("\nDone.", flush=True)
