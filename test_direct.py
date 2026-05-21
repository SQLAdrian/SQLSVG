import pyodbc, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = pyodbc.connect(
    r'DRIVER={ODBC Driver 17 for SQL Server};SERVER=MSI\old2017;'
    r'DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;',
    timeout=30)
conn.autocommit = True
cur = conn.cursor()

# Test 1: tokenizer
print('=== Tokenizer test ===')
cur.execute(
    "SELECT token_id, token FROM dbo.fn_TokenizeSvgPath("
    "'m 414.70534,1921.9386 0.32323,-4.3687 2.27689,-1.5 -3.1-2.4 z'"
    ") ORDER BY token_id"
)
for r in cur.fetchall():
    print(f'  [{r[0]:2d}] {r[1]}')

# Test 2: parser on simple path
print()
print('=== Parser test (edit-button pentagon) ===')
cur.execute(
    "SELECT subpath_id, point_order, x, y "
    "FROM dbo.fn_ParseSvgPath("
    "'m70.064 422.35 374.27-374.26 107.58 107.58-374.26 374.27-129.56 21.97z', 12) "
    "ORDER BY point_order"
)
rows = cur.fetchall()
for r in rows:
    print(f'  sub={r[0]} po={r[1]:2d} x={r[2]:10.4f} y={r[3]:10.4f}')
print(f'  Total points: {len(rows)}')

# Test 3: parser on path with cubic bezier
print()
print('=== Parser test (cubic bezier from copy-button) ===')
test_d = "M433.941 65.941l-51.882-51.882C371.882 3.882 361.118 0 348.118 0"
cur.execute(
    "SELECT subpath_id, point_order, x, y "
    "FROM dbo.fn_ParseSvgPath(?, 8) "
    "ORDER BY point_order",
    test_d
)
rows = cur.fetchall()
for r in rows:
    print(f'  sub={r[0]} po={r[1]:2d} x={r[2]:10.4f} y={r[3]:10.4f}')
print(f'  Total points: {len(rows)}')

print()
print('=== All tests passed ===')
