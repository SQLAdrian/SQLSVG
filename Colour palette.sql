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


 
SELECT idkey, t.geom, t.id + 1 FROM @SSMSColourPalette t ORDER BY idkey asc;