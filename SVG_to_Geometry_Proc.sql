/*Adrian Sullivan - 2026/05/21 wrapper proc for SVG -> geometry.
needs fn_TokenizeSvgPath, fn_ParseSvgPath, fn_ParseSvgTransform from SVG_to_Geometry.sql.
usage: EXEC dbo.SVG_to_Geometry N'C:\...\file.svg'.
composes nested <g transform="..."> chains up to 8 deep so Inkscape SVGs render correctly.*/
IF OBJECT_ID('dbo.SVG_to_Geometry') IS NOT NULL
    DROP PROCEDURE dbo.SVG_to_Geometry;
GO

CREATE PROCEDURE dbo.SVG_to_Geometry
    @svg_path       NVARCHAR(400),
    @flatten_steps  INT = 12,
    --1 = UnionAggregate everything into one row.  Complex SVGs can produce
    --a geometry the SSMS spatial tab refuses to render (too many points), so
    --leave at 0 for those and pick a label column to colour by instead.
    @single_layer   BIT = 0
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @xml XML;
    DECLARE @sql NVARCHAR(MAX) = N'
        SELECT @xml = CAST(BulkColumn AS XML)
        FROM OPENROWSET(BULK N''' + REPLACE(@svg_path, '''', '''''') + N''', SINGLE_BLOB) AS b';
    EXEC sp_executesql @sql, N'@xml XML OUTPUT', @xml = @xml OUTPUT;

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
            REPLACE(REPLACE(ISNULL(sr.txt, ''), CHAR(13), ''), CHAR(10), ''), '}')
        WHERE LTRIM(RTRIM(value)) LIKE '.%{%'
    ),
    css_parsed AS (
        SELECT
            LTRIM(RTRIM(SUBSTRING(cr.rule_frag,
                CHARINDEX('.', cr.rule_frag) + 1,
                CHARINDEX('{', cr.rule_frag) - CHARINDEX('.', cr.rule_frag) - 1
            ))) AS class_name,
            CASE WHEN CHARINDEX('fill:', cr.rule_frag) > 0
            THEN LTRIM(RTRIM(SUBSTRING(cr.rule_frag,
                CHARINDEX('fill:', cr.rule_frag) + 5,
                CASE WHEN CHARINDEX(';', cr.rule_frag, CHARINDEX('fill:', cr.rule_frag)) > 0
                     THEN CHARINDEX(';', cr.rule_frag, CHARINDEX('fill:', cr.rule_frag))
                     ELSE LEN(cr.rule_frag) + 1
                END - CHARINDEX('fill:', cr.rule_frag) - 5
            )))
            ELSE NULL END AS fill_raw
        FROM css_rules cr
        WHERE cr.rule_frag LIKE '.%{%'
    ),
    css_fills AS (
        SELECT class_name,
            CASE WHEN fill_raw IN ('none','transparent','inherit','initial') THEN NULL
                 WHEN fill_raw LIKE '#[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]' AND LEN(fill_raw) = 4
                 THEN SUBSTRING(fill_raw,2,1)+SUBSTRING(fill_raw,2,1)
                     +SUBSTRING(fill_raw,3,1)+SUBSTRING(fill_raw,3,1)
                     +SUBSTRING(fill_raw,4,1)+SUBSTRING(fill_raw,4,1)
                 WHEN fill_raw LIKE '#%' THEN SUBSTRING(fill_raw, 2, 6)
                 ELSE NULL END AS fill_hex
        FROM css_parsed WHERE fill_raw IS NOT NULL
    ),
    --SQL Server XQuery has no ancestor:: axis, so walk `..` up to 8 deep.
    --tx_p8 is the outermost <g> transform, tx_self is the path's own.
    --also pull the parent group's inkscape:label / id so SSMS can label rows.
    paths_raw AS (
        SELECT
            ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS layer_id,
            p.value('@id',   'VARCHAR(200)')  AS path_id,
            p.value('@style','NVARCHAR(MAX)') AS style_attr,
            p.value('@fill', 'VARCHAR(200)')  AS fill_attr,
            p.value('@class','VARCHAR(200)')  AS class_attr,
            p.value('@transform', 'VARCHAR(500)') AS tx_self,
            p.value('(../@transform)[1]',                       'VARCHAR(500)') AS tx_p1,
            p.value('(../../@transform)[1]',                    'VARCHAR(500)') AS tx_p2,
            p.value('(../../../@transform)[1]',                 'VARCHAR(500)') AS tx_p3,
            p.value('(../../../../@transform)[1]',              'VARCHAR(500)') AS tx_p4,
            p.value('(../../../../../@transform)[1]',           'VARCHAR(500)') AS tx_p5,
            p.value('(../../../../../../@transform)[1]',        'VARCHAR(500)') AS tx_p6,
            p.value('(../../../../../../../@transform)[1]',     'VARCHAR(500)') AS tx_p7,
            p.value('(../../../../../../../../@transform)[1]',  'VARCHAR(500)') AS tx_p8,
            p.value(
                'declare namespace inkscape="http://www.inkscape.org/namespaces/inkscape";
                 (../@inkscape:label)[1]', 'VARCHAR(200)') AS parent_label,
            p.value('(../@id)[1]', 'VARCHAR(200)') AS parent_id,
            p.value('@d',    'NVARCHAR(MAX)') AS d_attr
        FROM @xml.nodes(
            'declare default element namespace "http://www.w3.org/2000/svg"; //path'
        ) AS x(p)
    ),
    paths AS (
        SELECT pr.layer_id, pr.path_id, pr.d_attr,
            --prefer inkscape:label, fall back to the group's id, else NULL.
            COALESCE(NULLIF(pr.parent_label,''), NULLIF(pr.parent_id,'')) AS group_label,
            --concatenate outer-first; fn_ParseSvgTransform composes per SVG 7.6.
            LTRIM(RTRIM(
                ISNULL(pr.tx_p8,'') + ' ' +
                ISNULL(pr.tx_p7,'') + ' ' +
                ISNULL(pr.tx_p6,'') + ' ' +
                ISNULL(pr.tx_p5,'') + ' ' +
                ISNULL(pr.tx_p4,'') + ' ' +
                ISNULL(pr.tx_p3,'') + ' ' +
                ISNULL(pr.tx_p2,'') + ' ' +
                ISNULL(pr.tx_p1,'') + ' ' +
                ISNULL(pr.tx_self,'')
            )) AS tx_combined,
            CASE
                WHEN pr.style_attr LIKE '%fill:%' THEN
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
                ELSE NULL
            END AS fill_hex
        FROM paths_raw pr
        LEFT JOIN css_fills cf ON cf.class_name = pr.class_attr
    )
    SELECT layer_id, path_id, group_label, fill_hex, d_attr, tx_combined
    INTO #paths FROM paths
    WHERE d_attr IS NOT NULL AND LTRIM(RTRIM(d_attr)) <> '';

    --resolve matrix once per path, apply to every point, then SSMS y-flip.
    ;WITH paths_mtx AS (
        SELECT p.layer_id, p.d_attr,
               m.a, m.b, m.c, m.d, m.e, m.f
        FROM #paths p
        CROSS APPLY dbo.fn_ParseSvgTransform(p.tx_combined) m
    ),
    parsed AS (
        SELECT pm.layer_id, pts.subpath_id, pts.point_order,
                  pm.a * pts.x + pm.c * pts.y + pm.e  AS x,
                -(pm.b * pts.x + pm.d * pts.y + pm.f) AS y
        FROM paths_mtx pm
        CROSS APPLY dbo.fn_ParseSvgPath(pm.d_attr, @flatten_steps) pts
    ),
    ring_ends AS (
        SELECT layer_id, subpath_id,
               MIN(point_order) AS first_po, MAX(point_order) AS last_po
        FROM parsed GROUP BY layer_id, subpath_id
    ),
    closing_pts AS (
        SELECT re.layer_id, re.subpath_id, 999999 AS point_order, p.x, p.y
        FROM ring_ends re
        JOIN parsed p ON p.layer_id = re.layer_id AND p.subpath_id = re.subpath_id
                     AND p.point_order = re.first_po
    ),
    all_pts AS (
        SELECT * FROM parsed UNION ALL SELECT * FROM closing_pts
    ),
    rings AS (
        SELECT layer_id, subpath_id,
            STRING_AGG(
                CAST(CAST(CAST(x AS DECIMAL(18,6)) AS VARCHAR(32)) + ' ' +
                     CAST(CAST(y AS DECIMAL(18,6)) AS VARCHAR(32))
                     AS VARCHAR(MAX)),
                ','
            ) WITHIN GROUP (ORDER BY point_order) AS ring_coords,
            COUNT(DISTINCT
                CAST(CAST(x AS DECIMAL(18,6)) AS VARCHAR(32)) + ',' +
                CAST(CAST(y AS DECIMAL(18,6)) AS VARCHAR(32))) AS distinct_pts
        FROM all_pts
        GROUP BY layer_id, subpath_id
        HAVING COUNT(DISTINCT
            CAST(CAST(x AS DECIMAL(18,6)) AS VARCHAR(32)) + ',' +
            CAST(CAST(y AS DECIMAL(18,6)) AS VARCHAR(32))) >= 3
    ),
    wkt_shapes AS (
        SELECT layer_id,
            CASE WHEN COUNT(*) = 1
                 THEN 'POLYGON((' + MAX(ring_coords) + '))'
                 ELSE 'MULTIPOLYGON(' +
                      STRING_AGG('((' + ring_coords + '))', ',')
                          WITHIN GROUP (ORDER BY subpath_id) + ')'
            END AS wkt
        FROM rings GROUP BY layer_id
    )

    --materialise per-path geometries so IF/ELSE can branch on the output shape.
    SELECT
        p.layer_id,
        p.group_label,
        p.path_id,
        p.fill_hex,
        geometry::STGeomFromText(ws.wkt, 0).MakeValid() AS geom
    INTO #final
    FROM #paths p
    LEFT JOIN wkt_shapes ws ON ws.layer_id = p.layer_id;

    IF @single_layer = 0
        SELECT layer_id, group_label, path_id, fill_hex, geom
        FROM #final ORDER BY layer_id;
    ELSE
        SELECT 1                              AS layer_id,
               CAST(NULL AS VARCHAR(200))     AS group_label,
               CAST(NULL AS VARCHAR(200))     AS path_id,
               CAST(NULL AS VARCHAR(8))       AS fill_hex,
               geometry::UnionAggregate(geom) AS geom
        FROM #final
        WHERE geom IS NOT NULL;
END
GO
