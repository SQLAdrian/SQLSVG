import pyodbc, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
conn = pyodbc.connect(
    r'DRIVER={ODBC Driver 17 for SQL Server};SERVER=MSI\new2022;'
    r'DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;',
    timeout=30)
conn.autocommit = True
cur = conn.cursor()

svg = r'C:\GitHub\SVGme\Test\Simple.svg'

# First, just run the procedure alone to see if it works
print("Test 1: Procedure existence...")
cur.execute("SELECT OBJECT_ID('dbo.SVG_to_Geometry')")
oid = cur.fetchone()[0]
print(f"  Procedure OID: {oid}")

print("\nTest 2: Run procedure directly (expect geometry type error in pyodbc)...")
try:
    cur.execute("EXEC dbo.SVG_to_Geometry N'" + svg + "'")
    print("  No error! Rows:", cur.fetchall())
except Exception as e:
    err = str(e).split('\n')[0][:150]
    print(f"  Expected error: {err}")

print("\nTest 3: INSERT EXEC into temp table...")
try:
    cur.execute(
        "CREATE TABLE #tmp (layer_id INT, fill_hex VARCHAR(10), geom geometry); "
        "INSERT #tmp EXEC dbo.SVG_to_Geometry N'" + svg + "'; "
        "SELECT layer_id, fill_hex FROM #tmp ORDER BY layer_id"
    )
    print("  rows:", cur.fetchall())
except Exception as e:
    print(f"  ERROR: {e}")

# Now compare: get the original SVG d_attr values
cur.execute(
    "DECLARE @xml XML; "
    "SELECT @xml = CAST(BulkColumn AS XML) "
    "FROM OPENROWSET(BULK N'" + svg + "', SINGLE_BLOB) AS b; "
    "SELECT ROW_NUMBER() OVER (ORDER BY (SELECT NULL)), "
    "  p.value('@d', 'NVARCHAR(MAX)') "
    "FROM @xml.nodes('declare default element namespace \"http://www.w3.org/2000/svg\"; //path') AS x(p)"
)
print("\n=== Original SVG path data ===")
for r in cur.fetchall():
    d = r[1]
    if d and len(d) > 200:
        d = d[:200] + '...'
    print(f"  path {r[0]}: {d}")
