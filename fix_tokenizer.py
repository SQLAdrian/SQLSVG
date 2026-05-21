import pyodbc, sys, time, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = pyodbc.connect(
    r'DRIVER={ODBC Driver 17 for SQL Server};SERVER=MSI\new2022;'
    r'DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;',
    timeout=30)
conn.autocommit = True
cur = conn.cursor()

# Drop old function
cur.execute("IF OBJECT_ID('dbo.fn_TokenizeSvgPath') IS NOT NULL DROP FUNCTION dbo.fn_TokenizeSvgPath")
print("Dropped old function", flush=True)

# Read new function from file
with open(r'C:\GitHub\SVGme\SVG_to_Geometry.sql', 'r') as f:
    sql = f.read()

# Extract the tokenizer CREATE FUNCTION section
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
# Remove trailing GO
if tokenizer_sql.endswith('GO'):
    tokenizer_sql = tokenizer_sql[:-2].strip()

# Execute the CREATE FUNCTION
cur.execute(tokenizer_sql)
print("Created new tokenizer function", flush=True)

# Test it
print("Loading copy-button.svg...", flush=True)
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

print("Tokenizing...", flush=True)
t0 = time.time()
cur.execute("SELECT COUNT(*) FROM dbo.fn_TokenizeSvgPath(?)", d_attr)
n = cur.fetchone()[0]
print(f"  {n} tokens in {time.time()-t0:.2f}s", flush=True)

print("Tokens:", flush=True)
cur.execute("SELECT token_id, token FROM dbo.fn_TokenizeSvgPath(?) ORDER BY token_id", d_attr)
for r in cur.fetchall():
    print(f"  [{r[0]:3d}] {r[1]}", flush=True)

print("Done.", flush=True)
