"""
Test harness for SVG_to_Geometry.sql
Runs each SVG file through the parser and prints results.
Uses integrated auth against MSI\old2017.
"""
import pyodbc
import os
import re
import sys

SERVER   = r"MSI\old2017"
DATABASE = "master"
DRIVER   = "{ODBC Driver 17 for SQL Server}"
SVG_DIR  = r"C:\GitHub\SVGme"
SQL_FILE = os.path.join(SVG_DIR, "SVG_to_Geometry.sql")

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# -- helper: split SQL script on GO lines (batch separator) --------
def split_batches(sql_text):
    """Split on lines that are exactly 'GO' (case-insensitive)."""
    batches = []
    current = []
    for line in sql_text.splitlines():
        if re.match(r'^\s*GO\s*$', line, re.IGNORECASE):
            if current:
                batches.append('\n'.join(current))
                current = []
        else:
            current.append(line)
    if current:
        batches.append('\n'.join(current))
    return batches


def main():
    conn_str = (f"DRIVER={DRIVER};SERVER={SERVER};DATABASE={DATABASE};"
                f"Trusted_Connection=yes;TrustServerCertificate=yes;")
    print(f"Connecting to {SERVER}...")
    conn = pyodbc.connect(conn_str)
    conn.autocommit = True
    cursor = conn.cursor()

    # Print SQL Server version
    cursor.execute("SELECT @@VERSION")
    ver = cursor.fetchone()[0]
    print(f"Connected. SQL Server: {ver.split(chr(10))[0]}\n")

    # -- Read the SQL file ------------------------------------------
    with open(SQL_FILE, 'r', encoding='utf-8') as f:
        sql_text = f.read()

    # -- Split on GO -----------------------------------------------
    all_batches = split_batches(sql_text)
    print(f"Found {len(all_batches)} batches.\n")

    for idx, b in enumerate(all_batches):
        first = b.strip().split('\n')[0][:90] if b.strip() else '(empty)'
        print(f"  Batch {idx}: {first}")

    # -- Identify structure: batches before DECLARE @svg_path are
    #    function definitions; the batch with DECLARE @svg_path and
    #    everything after is the main script. ---------------------------------
    func_batches = []
    main_batches = []
    found_main = False
    for b in all_batches:
        if not found_main and re.search(r'DECLARE\s+@svg_path', b, re.IGNORECASE):
            found_main = True
        if found_main:
            main_batches.append(b)
        else:
            func_batches.append(b)

    print(f"\n  -> Function batches: {len(func_batches)}")
    print(f"  -> Main script batches: {len(main_batches)}\n")

    # -- Create functions -------------------------------------------
    print("=" * 60)
    print("STEP 1: Creating helper functions")
    print("=" * 60)
    for i, batch in enumerate(func_batches):
        first_line = batch.strip().split('\n')[0][:80]
        print(f"  Batch {i}: {first_line}")
        try:
            cursor.execute(batch)
            print(f"    OK")
        except Exception as e:
            err = str(e).split('\n')[0][:120]
            print(f"    ERROR: {err}")

    # -- Test the tokenizer with the spec's test string -------------
    print("\n" + "=" * 60)
    print("STEP 1b: Tokenizer self-test")
    print("=" * 60)
    test_d = r"m 414.70534,1921.9386 0.32323,-4.3687 2.27689,-1.5 -3.1-2.4 z"
    try:
        cursor.execute(
            "SELECT token_id, token FROM dbo.fn_TokenizeSvgPath(?) ORDER BY token_id",
            test_d
        )
        rows = cursor.fetchall()
        print(f"  Tokens for: {test_d}")
        for r in rows:
            print(f"    [{r[0]:2d}] {r[1]}")
    except Exception as e:
        err = str(e).split('\n')[0][:200]
        print(f"  ERROR: {err}")

    # -- Run main script for each SVG file -------------------------
    svg_files = sorted([f for f in os.listdir(SVG_DIR) if f.endswith('.svg')])

    for svg_file in svg_files:
        svg_path = os.path.join(SVG_DIR, svg_file)
        print(f"\n{'=' * 60}")
        print(f"STEP 2: {svg_file}")
        print("=" * 60)

        # Combine all main batches into a single script
        combined = '\n'.join(main_batches)

        # Replace the @svg_path value (use lambda to avoid backslash issues)
        combined = re.sub(
            r"DECLARE\s+@svg_path\s+NVARCHAR\(400\)\s*=\s*N'[^']*'",
            lambda m: f"DECLARE @svg_path NVARCHAR(400) = N'{svg_path}'",
            combined
        )

        # Execute the combined main script
        try:
            cursor.execute(combined)

            # Walk through result sets
            rs_num = 0
            while True:
                if cursor.description:
                    columns = [col[0] for col in cursor.description]
                    rows = cursor.fetchall()
                    rs_num += 1
                    print(f"\n  Result set #{rs_num} ({len(rows)} rows):")
                    for row in rows:
                        layer_id = row[0]
                        fill_hex = row[1]
                        geom = row[2]
                        geom_wkt = None
                        if geom is not None:
                            try:
                                geom_wkt = geom.STAsText()
                                if len(geom_wkt) > 120:
                                    geom_wkt = geom_wkt[:120] + "..."
                            except Exception:
                                geom_wkt = str(geom)[:100]
                        print(f"    layer={layer_id}  fill=#{fill_hex or 'none':8s}  "
                              f"geom={geom_wkt or 'NULL'}")
                    if not rows:
                        print("    (no rows)")

                if not cursor.nextset():
                    break

            if rs_num == 0:
                print("  (no result sets)")

        except Exception as e:
            err = str(e).split('\n')[:3]
            print(f"  ERROR:")
            for line in err:
                print(f"    {line[:150]}")

    print(f"\n{'=' * 60}")
    print("DONE")
    print("=" * 60)
    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
