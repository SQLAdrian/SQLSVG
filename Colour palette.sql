--https://alastaira.wordpress.com/2011/03/31/more-drawing-fun-with-sql-server/


DECLARE @SSMSColourPalette table (idkey INT identity(1,1), id int, geom geometry)
 DECLARE @x int = 0, @y int = 0;
 WHILE @y < 30
 BEGIN
 WHILE @x < 30
 BEGIN
 INSERT INTO @SSMSColourPalette VALUES(
 @y*10 + @x,
 'POLYGON((' + cast(@x AS varchar(32)) + ' ' + cast(@y AS varchar(32)) + ','
 + cast(@x + 1.5 AS varchar(32)) + ' ' + cast(@y AS varchar(32)) + ','
 + cast(@x - 0.8 AS varchar(32)) + ' ' + cast(@y + 1 AS varchar(32)) + ','
 + cast(@x AS varchar(32)) + ' ' + cast(@y + 1.5 AS varchar(32)) + ','
 + cast(@x AS varchar(32)) + ' ' + cast(@y AS varchar(32)) + '))'
 )
 SET @x = @x + 1;
 END
 SET @x = 0;
 SET @y = @y + 1;
 END


 
SELECT idkey, t.geom, t.id + 1 FROM @SSMSColourPalette t ORDER BY idkey asc;
go


DECLARE @SSMSColourPalette table (idkey INT identity(1,1), id int, geom geometry)
 DECLARE @x int = 0, @y int = 0;
 WHILE @y < 60
 BEGIN
 WHILE @x < 60
 BEGIN
 INSERT INTO @SSMSColourPalette VALUES(
 @y*10 + @x,
 'POLYGON((' + cast(@x AS varchar(32)) + ' ' + cast(@y AS varchar(32)) + ','
 + cast(@x + 1 AS varchar(32)) + ' ' + cast(@y + 1 AS varchar(32)) + ','
 + cast(@x + 1 AS varchar(32)) + ' ' + cast(@y + 1.2 AS varchar(32)) + ','
 + cast(@x - 1 AS varchar(32)) + ' ' + cast(@y + 1 AS varchar(32)) + ','
 + cast(@x AS varchar(32)) + ' ' + cast(@y AS varchar(32)) + '))'
 )
 SET @x = @x + 1;
 END
 SET @x = 0;
 SET @y = @y + 1;
 END


 
SELECT idkey, t.geom, t.id + 1 FROM @SSMSColourPalette t ORDER BY idkey asc;GO

/*32-square strip in two stacked rows of 16 - clean palette extractor.
no overlap, large squares so the centre RGB is easy to eyedrop.
two full cycles let you confirm the palette period before sampling.*/
DECLARE @PaletteStrip TABLE (idkey INT IDENTITY(1,1), label VARCHAR(8), geom GEOMETRY);
DECLARE @i INT = 0;
WHILE @i < 32
BEGIN
    DECLARE @col INT = @i % 16;
    DECLARE @row INT = @i / 16;
    DECLARE @x0 FLOAT = @col * 3.0;
    DECLARE @y0 FLOAT = @row * 3.0;
    INSERT INTO @PaletteStrip(label, geom) VALUES (
        'c' + RIGHT('00' + CAST(@i + 1 AS VARCHAR(3)), 3),
        geometry::STGeomFromText(
            'POLYGON((' +
            CAST(@x0       AS VARCHAR(32)) + ' ' + CAST(@y0       AS VARCHAR(32)) + ',' +
            CAST(@x0 + 2.0 AS VARCHAR(32)) + ' ' + CAST(@y0       AS VARCHAR(32)) + ',' +
            CAST(@x0 + 2.0 AS VARCHAR(32)) + ' ' + CAST(@y0 + 2.0 AS VARCHAR(32)) + ',' +
            CAST(@x0       AS VARCHAR(32)) + ' ' + CAST(@y0 + 2.0 AS VARCHAR(32)) + ',' +
            CAST(@x0       AS VARCHAR(32)) + ' ' + CAST(@y0       AS VARCHAR(32)) + '))',
            0)
    );
    SET @i += 1;
END

SELECT label, geom FROM @PaletteStrip ORDER BY idkey;
GO

/*Scriptable palette probe.
Edit @grid_size then F5.  Default 32 -> 1024 singletons + 32 overlap
pair cells = 1056 rows.

Layout:
  - NxN singleton grid at y >= 0 (rows 1..N^2).
    Cell (col, row) is positioned at (col*3, row*3), 2x2 unit square.
    Result row order is left-to-right then bottom-to-top, so result
    row R corresponds to col = (R-1) mod N, row = (R-1) / N in spatial.
  - N-cell overlap strip at y = -6..-4 (rows N^2+1 .. N^2+2N).
    For cell j (0..N-1): bottom polygon at row N^2+2j+1, top polygon
    at row N^2+2j+2, both at the same position.  Visible composite
    answers: does SSMS overlay opaque or translucent?

Pair the output with extract-palette.ps1 to dump a CSV of every
cell's RGB.  See PALETTE_EXTRACTION.md for the full workflow.*/
DECLARE @grid_size INT = 32;
DECLARE @P TABLE (idkey INT IDENTITY(1,1), label VARCHAR(12), geom GEOMETRY);

DECLARE @i INT = 0;
WHILE @i < @grid_size * @grid_size
BEGIN
    DECLARE @col INT = @i % @grid_size;
    DECLARE @row INT = @i / @grid_size;
    DECLARE @x0 FLOAT = @col * 3.0;
    DECLARE @y0 FLOAT = @row * 3.0;
    INSERT INTO @P(label, geom) VALUES (
        'r' + RIGHT('0000' + CAST(@i + 1 AS VARCHAR(5)), 4),
        geometry::STGeomFromText(
            'POLYGON((' +
            CAST(@x0       AS VARCHAR(32)) + ' ' + CAST(@y0       AS VARCHAR(32)) + ',' +
            CAST(@x0 + 2.0 AS VARCHAR(32)) + ' ' + CAST(@y0       AS VARCHAR(32)) + ',' +
            CAST(@x0 + 2.0 AS VARCHAR(32)) + ' ' + CAST(@y0 + 2.0 AS VARCHAR(32)) + ',' +
            CAST(@x0       AS VARCHAR(32)) + ' ' + CAST(@y0 + 2.0 AS VARCHAR(32)) + ',' +
            CAST(@x0       AS VARCHAR(32)) + ' ' + CAST(@y0       AS VARCHAR(32)) + '))',
            0)
    );
    SET @i += 1;
END

--Overlap strip: N pair-stacks at y = -6..-4, x = j*3 .. j*3+2.
DECLARE @j INT = 0;
WHILE @j < @grid_size
BEGIN
    DECLARE @bx FLOAT = @j * 3.0;
    DECLARE @by FLOAT = -6.0;
    --bottom layer
    INSERT INTO @P(label, geom) VALUES (
        'p' + RIGHT('000' + CAST(@j+1 AS VARCHAR(4)), 3) + 'b',
        geometry::STGeomFromText(
            'POLYGON((' +
            CAST(@bx       AS VARCHAR(32)) + ' ' + CAST(@by       AS VARCHAR(32)) + ',' +
            CAST(@bx + 2.0 AS VARCHAR(32)) + ' ' + CAST(@by       AS VARCHAR(32)) + ',' +
            CAST(@bx + 2.0 AS VARCHAR(32)) + ' ' + CAST(@by + 2.0 AS VARCHAR(32)) + ',' +
            CAST(@bx       AS VARCHAR(32)) + ' ' + CAST(@by + 2.0 AS VARCHAR(32)) + ',' +
            CAST(@bx       AS VARCHAR(32)) + ' ' + CAST(@by       AS VARCHAR(32)) + '))',
            0)
    );
    --top layer, identical coords
    INSERT INTO @P(label, geom) VALUES (
        'p' + RIGHT('000' + CAST(@j+1 AS VARCHAR(4)), 3) + 't',
        geometry::STGeomFromText(
            'POLYGON((' +
            CAST(@bx       AS VARCHAR(32)) + ' ' + CAST(@by       AS VARCHAR(32)) + ',' +
            CAST(@bx + 2.0 AS VARCHAR(32)) + ' ' + CAST(@by       AS VARCHAR(32)) + ',' +
            CAST(@bx + 2.0 AS VARCHAR(32)) + ' ' + CAST(@by + 2.0 AS VARCHAR(32)) + ',' +
            CAST(@bx       AS VARCHAR(32)) + ' ' + CAST(@by + 2.0 AS VARCHAR(32)) + ',' +
            CAST(@bx       AS VARCHAR(32)) + ' ' + CAST(@by       AS VARCHAR(32)) + '))',
            0)
    );
    SET @j += 1;
END

SELECT label, geom FROM @P ORDER BY idkey;
