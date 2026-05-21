import pyodbc, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = pyodbc.connect(
    r'DRIVER={ODBC Driver 17 for SQL Server};SERVER=MSI\old2017;'
    r'DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;',
    timeout=30)
conn.autocommit = True
cur = conn.cursor()

# Test 1: numbers table CTE speed
print("Test 1: Numbers table CTE (65K rows)...", flush=True)
t0 = time.time()
cur.execute(
    "WITH L0 AS (SELECT 1 AS c UNION ALL SELECT 1), "
    "L1 AS (SELECT 1 AS c FROM L0 a CROSS JOIN L0 b), "
    "L2 AS (SELECT 1 AS c FROM L1 a CROSS JOIN L1 b), "
    "L3 AS (SELECT 1 AS c FROM L2 a CROSS JOIN L2 b), "
    "L4 AS (SELECT 1 AS c FROM L3 a CROSS JOIN L3 b), "
    "nums AS (SELECT ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS n FROM L4) "
    "SELECT COUNT(*) FROM nums WHERE n <= 600"
)
print(f"  Count: {cur.fetchone()[0]}, Time: {time.time()-t0:.2f}s", flush=True)

# Test 2: tokenizer with 66-char string (known fast)
print("\nTest 2: Tokenizer 66 chars...", flush=True)
t0 = time.time()
cur.execute(
    "SELECT COUNT(*) FROM dbo.fn_TokenizeSvgPath("
    "'m 414.70534,1921.9386 0.32323,-4.3687 2.27689,-1.5 -3.1-2.4 z')"
)
print(f"  Count: {cur.fetchone()[0]}, Time: {time.time()-t0:.2f}s", flush=True)

# Test 3: tokenizer with 200-char string
print("\nTest 3: Tokenizer ~200 chars...", flush=True)
d200 = "M100 200L300 400C500 600 700 800 900 1000 " * 4
t0 = time.time()
cur.execute("SELECT COUNT(*) FROM dbo.fn_TokenizeSvgPath(?)", d200)
print(f"  Count: {cur.fetchone()[0]}, Time: {time.time()-t0:.2f}s", flush=True)

# Test 4: tokenizer with 500-char string
print("\nTest 4: Tokenizer ~500 chars...", flush=True)
d500 = "M433.941 65.941l-51.882-51.882A48 48 0 0 0 348.118 0H176c-26.51 0-48 21.49-48 48v48H48 " * 4
t0 = time.time()
try:
    cur.execute("SELECT COUNT(*) FROM dbo.fn_TokenizeSvgPath(?)", d500)
    print(f"  Count: {cur.fetchone()[0]}, Time: {time.time()-t0:.2f}s", flush=True)
except Exception as e:
    print(f"  ERROR after {time.time()-t0:.2f}s: {e}", flush=True)

# Test 5: tokenizer with actual copy-button d_attr
print("\nTest 5: Tokenizer copy-button.svg (508 chars)...", flush=True)
cur.execute(
    "DECLARE @xml XML; "
    "SELECT @xml = CAST(BulkColumn AS XML) "
    "FROM OPENROWSET(BULK N'C:\\GitHub\\SVGme\\copy-button.svg', SINGLE_BLOB) AS b; "
    "SELECT p.value('@d','NVARCHAR(MAX)') "
    "FROM @xml.nodes("
    "'declare default element namespace \"http://www.w3.org/2000/svg\"; //path'"
    ") AS x(p)"
)
d_actual = cur.fetchone()[0]
print(f"  d_attr: {len(d_actual)} chars", flush=True)
t0 = time.time()
try:
    cur.execute("SELECT COUNT(*) FROM dbo.fn_TokenizeSvgPath(?)", d_actual)
    print(f"  Count: {cur.fetchone()[0]}, Time: {time.time()-t0:.2f}s", flush=True)
except Exception as e:
    print(f"  ERROR after {time.time()-t0:.2f}s: {e}", flush=True)

print("\nDone.", flush=True)
