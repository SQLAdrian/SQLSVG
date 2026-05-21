/*Adrian Sullivan - 2026/05/21 SVG path -> SQL Server geometry, no CLR.
Thanks to https://www.sqldba.org/post/drawing-in-sql-server-using-ssms-a-technical-article for the original idea.
SRID 0, SQL Server 2017+. Edit @svg_path near the bottom and run.*/

/*tokeniser*/
IF OBJECT_ID('dbo.fn_TokenizeSvgPath') IS NOT NULL
    DROP FUNCTION dbo.fn_TokenizeSvgPath;
GO

--input: a path d-attribute. output: one row per token (command or number).
--normalise commas/command letters/sign-as-separator, then split on space in a WHILE loop.
--earlier 65K-row cross-join version hung on >100-char paths.
--double-dot tokens (0.6.5 -> 0.6 + .5) are split in a second pass below.
CREATE FUNCTION dbo.fn_TokenizeSvgPath (@d NVARCHAR(MAX))
RETURNS @tokens TABLE (token_id INT, token VARCHAR(200))
AS
BEGIN
    IF @d IS NULL OR @d = '' RETURN;

    SET @d = REPLACE(@d, ',', ' ');

    --case-sensitive collation: default is often CI which collapses 'M' and 'm'.
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'Z',' Z ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'z',' z ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'M',' M ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'm',' m ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'L',' L ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'l',' l ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'H',' H ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'h',' h ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'V',' V ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'v',' v ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'C',' C ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'c',' c ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'S',' S ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 's',' s ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'Q',' Q ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'q',' q ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'T',' T ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 't',' t ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'A',' A ');
    SET @d = REPLACE(@d COLLATE Latin1_General_BIN, 'a',' a ');

    --protect scientific notation before the blanket sign-as-separator pass.
    SET @d = REPLACE(@d, 'e-', CHAR(1));
    SET @d = REPLACE(@d, 'e+', CHAR(2));
    SET @d = REPLACE(@d, 'E-', CHAR(3));
    SET @d = REPLACE(@d, 'E+', CHAR(4));

    --sign-as-separator: "3.1-2.4" -> "3.1 -2.4".
    SET @d = REPLACE(@d, '0-','0 -');   SET @d = REPLACE(@d, '1-','1 -');
    SET @d = REPLACE(@d, '2-','2 -');   SET @d = REPLACE(@d, '3-','3 -');
    SET @d = REPLACE(@d, '4-','4 -');   SET @d = REPLACE(@d, '5-','5 -');
    SET @d = REPLACE(@d, '6-','6 -');   SET @d = REPLACE(@d, '7-','7 -');
    SET @d = REPLACE(@d, '8-','8 -');   SET @d = REPLACE(@d, '9-','9 -');
    SET @d = REPLACE(@d, '.-','. -');
    SET @d = REPLACE(@d, '+', ' +');

    SET @d = REPLACE(@d, CHAR(1), 'e-');
    SET @d = REPLACE(@d, CHAR(2), 'e+');
    SET @d = REPLACE(@d, CHAR(3), 'E-');
    SET @d = REPLACE(@d, CHAR(4), 'E+');

    WHILE CHARINDEX('  ', @d) > 0
        SET @d = REPLACE(@d, '  ', ' ');
    SET @d = LTRIM(RTRIM(@d));

    --split on space, O(n).
    DECLARE @pos  INT = 1;
    DECLARE @next INT;
    DECLARE @tok  VARCHAR(200);
    DECLARE @tid  INT = 1;

    WHILE @pos <= LEN(@d)
    BEGIN
        WHILE @pos <= LEN(@d) AND SUBSTRING(@d, @pos, 1) = ' '
            SET @pos = @pos + 1;
        IF @pos > LEN(@d) BREAK;

        SET @next = CHARINDEX(' ', @d, @pos);
        IF @next = 0 SET @next = LEN(@d) + 1;

        SET @tok = SUBSTRING(@d, @pos, @next - @pos);
        IF @tok <> ''
        BEGIN
            INSERT INTO @tokens VALUES (@tid, @tok);
            SET @tid = @tid + 1;
        END

        SET @pos = @next + 1;
    END

    --double-dot split: a single token "0.6.5" becomes "0.6" and ".5".
    DECLARE @fix TABLE (old_tid INT, new_tid INT, token VARCHAR(200));
    DECLARE @dot_count INT;
    DECLARE @cpos INT;
    DECLARE @dot_seen BIT;
    DECLARE @ch CHAR(1);
    DECLARE @cur VARCHAR(200);

    DECLARE c CURSOR LOCAL FAST_FORWARD FOR
        SELECT token_id, token,
               CASE WHEN token IN ('M','m','L','l','H','h','V','v',
                                   'C','c','S','s','Q','q','T','t','A','a','Z','z')
                    THEN 0
                    ELSE LEN(token) - LEN(REPLACE(token, '.', ''))
               END
        FROM @tokens;

    OPEN c;
    FETCH NEXT FROM c INTO @tid, @tok, @dot_count;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        IF @dot_count <= 1
        BEGIN
            INSERT INTO @fix VALUES (@tid, @tid, @tok);
        END
        ELSE
        BEGIN
            --start a new number at each '.' that follows a digit, when we've already seen one.
            SET @dot_seen = 0;
            SET @cur = '';
            SET @cpos = 1;

            WHILE @cpos <= LEN(@tok)
            BEGIN
                SET @ch = SUBSTRING(@tok, @cpos, 1);

                IF @ch = '.' AND @cpos > 1
                   AND SUBSTRING(@tok, @cpos-1, 1) BETWEEN '0' AND '9'
                   AND @dot_seen = 1
                BEGIN
                    INSERT INTO @fix VALUES (@tid, @tid + @cpos, @cur);
                    SET @cur = '.';
                    SET @dot_seen = 0;
                END
                ELSE
                BEGIN
                    SET @cur = @cur + @ch;
                    IF @ch = '.' SET @dot_seen = 1;
                END

                SET @cpos = @cpos + 1;
            END

            IF @cur <> ''
                INSERT INTO @fix VALUES (@tid, @tid + @cpos, @cur);
        END

        FETCH NEXT FROM c INTO @tid, @tok, @dot_count;
    END
    CLOSE c;
    DEALLOCATE c;

    DELETE FROM @tokens;
    INSERT INTO @tokens (token_id, token)
    SELECT ROW_NUMBER() OVER (ORDER BY new_tid, token) AS token_id, token
    FROM @fix;

    RETURN;
END
GO

/*parser*/
IF OBJECT_ID('dbo.fn_ParseSvgPath') IS NOT NULL
    DROP FUNCTION dbo.fn_ParseSvgPath;
GO

--walks the token stream as a state machine and emits absolute (x,y) points.
--all 20 SVG commands: M m L l H h V v C c S s Q q T t A a Z z.
--curves are flattened to @flatten_steps line segments.
--multiple M commands inside one d-attribute become separate subpaths -> MULTIPOLYGON.
CREATE FUNCTION dbo.fn_ParseSvgPath (
    @d              NVARCHAR(MAX),
    @flatten_steps  INT = 12
)
RETURNS @points TABLE (
    point_order  INT IDENTITY(1,1),
    subpath_id   INT,
    x            FLOAT,
    y            FLOAT
)
AS
BEGIN
    DECLARE @tokens TABLE (tid INT PRIMARY KEY, token VARCHAR(200));
    INSERT INTO @tokens (tid, token)
    SELECT token_id, token FROM dbo.fn_TokenizeSvgPath(@d);

    DECLARE @max_tid INT = (SELECT MAX(tid) FROM @tokens);
    IF @max_tid IS NULL RETURN;

    DECLARE @i        INT = 1;
    DECLARE @cmd      CHAR(1) = '';
    DECLARE @cx       FLOAT = 0,  @cy  FLOAT = 0;   --current point
    DECLARE @sx       FLOAT = 0,  @sy  FLOAT = 0;   --subpath start, for Z
    DECLARE @sub_id   INT   = 0;
    DECLARE @is_first_cmd BIT = 1;
    DECLARE @orig_m_rel   BIT = 0;                  --was the initial m lowercase?

    DECLARE @cpx FLOAT = 0, @cpy FLOAT = 0;         --prev curve's last ctrl point
    DECLARE @cubic_prev BIT = 0;
    DECLARE @quad_prev  BIT = 0;

    DECLARE @token VARCHAR(200);
    DECLARE @nx FLOAT, @ny FLOAT;
    DECLARE @x1 FLOAT, @y1 FLOAT, @x2 FLOAT, @y2 FLOAT;
    DECLARE @rx FLOAT, @ry FLOAT, @xrot FLOAT;
    DECLARE @fA INT, @fS INT;
    DECLARE @t FLOAT, @bx FLOAT, @by FLOAT;
    DECLARE @step INT;
    DECLARE @prev_i INT = 0;

    WHILE @i <= @max_tid
    BEGIN
        SET @token = (SELECT token FROM @tokens WHERE tid = @i);

        -- ── Is this a command letter? ─────────────────────────────
        IF @token IN ('M','m','L','l','H','h','V','v',
                      'C','c','S','s','Q','q','T','t',
                      'A','a','Z','z')
        BEGIN
            SET @cmd = @token;
            SET @i += 1;

            -- Z / z : close path, no arguments
            IF @cmd IN ('Z','z')
            BEGIN
                INSERT INTO @points (subpath_id, x, y)
                VALUES (@sub_id, @sx, @sy);
                SET @cx = @sx; SET @cy = @sy;
                SET @cubic_prev = 0; SET @quad_prev = 0;
                CONTINUE;
            END
        END

        --skip stray command letters mid-stream (will pick them up next loop).
        IF @token IN ('M','m','L','l','H','h','V','v',
                      'C','c','S','s','Q','q','T','t',
                      'A','a','Z','z')
            CONTINUE;

        --M / m  moveto
        IF @cmd IN ('M','m')
        BEGIN
            SET @nx = TRY_CAST((SELECT token FROM @tokens WHERE tid=@i  ) AS FLOAT);
            SET @ny = TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+1) AS FLOAT);
            IF @nx IS NULL OR @ny IS NULL BEGIN SET @i += 1; CONTINUE; END

            --first m in a path is absolute (SVG 9.3.3).
            --COLLATE forces case-sensitive compare regardless of DB collation.
            IF @is_first_cmd = 1 AND @cmd COLLATE Latin1_General_BIN = 'm'
            BEGIN
                SET @is_first_cmd = 0;
                SET @orig_m_rel = 1;
            END
            ELSE IF @cmd COLLATE Latin1_General_BIN = 'm'
            BEGIN
                SET @nx = @cx + @nx; SET @ny = @cy + @ny;
            END

            SET @is_first_cmd = 0;
            SET @sub_id += 1;
            SET @cx = @nx; SET @cy = @ny;
            SET @sx = @cx; SET @sy = @cy;
            INSERT INTO @points (subpath_id, x, y) VALUES (@sub_id, @cx, @cy);
            SET @i += 2;

            --subsequent pairs become implicit L / l.
            SET @cmd = CASE WHEN @cmd COLLATE Latin1_General_BIN = 'M' THEN 'L'
                            WHEN @orig_m_rel = 1 THEN 'l'
                            ELSE 'l' END;
            SET @orig_m_rel = 0;
            CONTINUE;
        END

        --L / l  lineto
        IF @cmd IN ('L','l')
        BEGIN
            SET @nx = TRY_CAST((SELECT token FROM @tokens WHERE tid=@i  ) AS FLOAT);
            SET @ny = TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+1) AS FLOAT);
            IF @nx IS NULL OR @ny IS NULL BEGIN SET @i += 1; CONTINUE; END
            IF @cmd COLLATE Latin1_General_BIN ='l' BEGIN SET @nx=@cx+@nx; SET @ny=@cy+@ny; END
            SET @cx=@nx; SET @cy=@ny;
            INSERT INTO @points (subpath_id, x, y) VALUES (@sub_id, @cx, @cy);
            SET @i += 2; SET @cubic_prev=0; SET @quad_prev=0;
            CONTINUE;
        END

        --H / h  horizontal lineto
        IF @cmd IN ('H','h')
        BEGIN
            SET @nx = TRY_CAST((SELECT token FROM @tokens WHERE tid=@i) AS FLOAT);
            IF @nx IS NULL BEGIN SET @i += 1; CONTINUE; END
            IF @cmd COLLATE Latin1_General_BIN ='h' SET @nx = @cx + @nx;
            SET @cx = @nx;
            INSERT INTO @points (subpath_id, x, y) VALUES (@sub_id, @cx, @cy);
            SET @i += 1; SET @cubic_prev=0; SET @quad_prev=0;
            CONTINUE;
        END

        --V / v  vertical lineto
        IF @cmd IN ('V','v')
        BEGIN
            SET @ny = TRY_CAST((SELECT token FROM @tokens WHERE tid=@i) AS FLOAT);
            IF @ny IS NULL BEGIN SET @i += 1; CONTINUE; END
            IF @cmd COLLATE Latin1_General_BIN ='v' SET @ny = @cy + @ny;
            SET @cy = @ny;
            INSERT INTO @points (subpath_id, x, y) VALUES (@sub_id, @cx, @cy);
            SET @i += 1; SET @cubic_prev=0; SET @quad_prev=0;
            CONTINUE;
        END

        --C / c  cubic Bezier  (x1 y1 x2 y2 x y)
        IF @cmd IN ('C','c')
        BEGIN
            SET @x1=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i  )AS FLOAT);
            SET @y1=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+1)AS FLOAT);
            SET @x2=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+2)AS FLOAT);
            SET @y2=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+3)AS FLOAT);
            SET @nx=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+4)AS FLOAT);
            SET @ny=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+5)AS FLOAT);
            IF @x1 IS NULL BEGIN SET @i+=1; CONTINUE; END

            IF @cmd COLLATE Latin1_General_BIN ='c' BEGIN
                SET @x1=@cx+@x1; SET @y1=@cy+@y1;
                SET @x2=@cx+@x2; SET @y2=@cy+@y2;
                SET @nx=@cx+@nx; SET @ny=@cy+@ny;
            END

            --flatten the cubic B(t) into @flatten_steps line segments.
            SET @step = 1;
            WHILE @step <= @flatten_steps
            BEGIN
                SET @t = CAST(@step AS FLOAT) / @flatten_steps;
                SET @bx = POWER(1-@t,3)*@cx
                        + 3*POWER(1-@t,2)*@t*@x1
                        + 3*(1-@t)*POWER(@t,2)*@x2
                        + POWER(@t,3)*@nx;
                SET @by = POWER(1-@t,3)*@cy
                        + 3*POWER(1-@t,2)*@t*@y1
                        + 3*(1-@t)*POWER(@t,2)*@y2
                        + POWER(@t,3)*@ny;
                INSERT INTO @points (subpath_id, x, y) VALUES (@sub_id, @bx, @by);
                SET @step += 1;
            END

            SET @cx=@nx; SET @cy=@ny;
            SET @cpx=@x2; SET @cpy=@y2;      --remembered for S reflection
            SET @cubic_prev=1; SET @quad_prev=0;
            SET @i += 6; CONTINUE;
        END

        --S / s  smooth cubic.  first ctrl point reflects previous cp2 (SVG 9.5.2).
        IF @cmd IN ('S','s')
        BEGIN
            SET @x2=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i  )AS FLOAT);
            SET @y2=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+1)AS FLOAT);
            SET @nx=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+2)AS FLOAT);
            SET @ny=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+3)AS FLOAT);
            IF @x2 IS NULL BEGIN SET @i+=1; CONTINUE; END

            IF @cmd COLLATE Latin1_General_BIN ='s' BEGIN
                SET @x2=@cx+@x2; SET @y2=@cy+@y2;
                SET @nx=@cx+@nx; SET @ny=@cy+@ny;
            END

            IF @cubic_prev=1 BEGIN
                SET @x1 = 2*@cx - @cpx; SET @y1 = 2*@cy - @cpy;
            END ELSE BEGIN
                SET @x1 = @cx; SET @y1 = @cy;
            END

            SET @step = 1;
            WHILE @step <= @flatten_steps
            BEGIN
                SET @t = CAST(@step AS FLOAT) / @flatten_steps;
                SET @bx = POWER(1-@t,3)*@cx + 3*POWER(1-@t,2)*@t*@x1
                        + 3*(1-@t)*POWER(@t,2)*@x2 + POWER(@t,3)*@nx;
                SET @by = POWER(1-@t,3)*@cy + 3*POWER(1-@t,2)*@t*@y1
                        + 3*(1-@t)*POWER(@t,2)*@y2 + POWER(@t,3)*@ny;
                INSERT INTO @points (subpath_id, x, y) VALUES (@sub_id, @bx, @by);
                SET @step += 1;
            END

            SET @cx=@nx; SET @cy=@ny;
            SET @cpx=@x2; SET @cpy=@y2;
            SET @cubic_prev=1; SET @quad_prev=0;
            SET @i += 4; CONTINUE;
        END

        --Q / q  quadratic Bezier  (x1 y1 x y)
        IF @cmd IN ('Q','q')
        BEGIN
            SET @x1=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i  )AS FLOAT);
            SET @y1=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+1)AS FLOAT);
            SET @nx=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+2)AS FLOAT);
            SET @ny=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+3)AS FLOAT);
            IF @x1 IS NULL BEGIN SET @i+=1; CONTINUE; END

            IF @cmd COLLATE Latin1_General_BIN ='q' BEGIN
                SET @x1=@cx+@x1; SET @y1=@cy+@y1;
                SET @nx=@cx+@nx; SET @ny=@cy+@ny;
            END

            SET @step = 1;
            WHILE @step <= @flatten_steps
            BEGIN
                SET @t = CAST(@step AS FLOAT) / @flatten_steps;
                SET @bx = POWER(1-@t,2)*@cx + 2*(1-@t)*@t*@x1 + POWER(@t,2)*@nx;
                SET @by = POWER(1-@t,2)*@cy + 2*(1-@t)*@t*@y1 + POWER(@t,2)*@ny;
                INSERT INTO @points (subpath_id, x, y) VALUES (@sub_id, @bx, @by);
                SET @step += 1;
            END

            SET @cx=@nx; SET @cy=@ny;
            SET @cpx=@x1; SET @cpy=@y1;      --remembered for T reflection
            SET @cubic_prev=0; SET @quad_prev=1;
            SET @i += 4; CONTINUE;
        END

        --T / t  smooth quadratic  (x y)
        IF @cmd IN ('T','t')
        BEGIN
            SET @nx=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i  )AS FLOAT);
            SET @ny=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+1)AS FLOAT);
            IF @nx IS NULL BEGIN SET @i+=1; CONTINUE; END

            IF @cmd COLLATE Latin1_General_BIN ='t' BEGIN SET @nx=@cx+@nx; SET @ny=@cy+@ny; END

            IF @quad_prev=1 BEGIN
                SET @x1 = 2*@cx - @cpx; SET @y1 = 2*@cy - @cpy;
            END ELSE BEGIN
                SET @x1 = @cx; SET @y1 = @cy;
            END

            SET @step = 1;
            WHILE @step <= @flatten_steps
            BEGIN
                SET @t = CAST(@step AS FLOAT) / @flatten_steps;
                SET @bx = POWER(1-@t,2)*@cx + 2*(1-@t)*@t*@x1 + POWER(@t,2)*@nx;
                SET @by = POWER(1-@t,2)*@cy + 2*(1-@t)*@t*@y1 + POWER(@t,2)*@ny;
                INSERT INTO @points (subpath_id, x, y) VALUES (@sub_id, @bx, @by);
                SET @step += 1;
            END

            SET @cx=@nx; SET @cy=@ny;
            SET @cpx=@x1; SET @cpy=@y1;
            SET @cubic_prev=0; SET @quad_prev=1;
            SET @i += 2; CONTINUE;
        END

        --A / a  elliptical arc.  endpoint-to-centre parameterisation per SVG B.2.4.
        IF @cmd IN ('A','a')
        BEGIN
            SET @rx  =TRY_CAST((SELECT token FROM @tokens WHERE tid=@i  )AS FLOAT);
            SET @ry  =TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+1)AS FLOAT);
            SET @xrot=TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+2)AS FLOAT);
            SET @fA  =TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+3)AS INT);
            SET @fS  =TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+4)AS INT);
            SET @nx  =TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+5)AS FLOAT);
            SET @ny  =TRY_CAST((SELECT token FROM @tokens WHERE tid=@i+6)AS FLOAT);
            IF @rx IS NULL BEGIN SET @i+=1; CONTINUE; END

            IF @cmd COLLATE Latin1_General_BIN ='a' BEGIN SET @nx=@cx+@nx; SET @ny=@cy+@ny; END

            --zero-length arc or zero radii: degenerate to a straight line.
            IF (@nx=@cx AND @ny=@cy) OR @rx=0 OR @ry=0
            BEGIN
                IF @nx<>@cx OR @ny<>@cy
                    INSERT INTO @points (subpath_id, x, y) VALUES (@sub_id, @nx, @ny);
                SET @cx=@nx; SET @cy=@ny;
                SET @i+=7; SET @cubic_prev=0; SET @quad_prev=0;
                CONTINUE;
            END

            --(x1', y1') in rotated space.
            DECLARE @phi FLOAT = RADIANS(@xrot);
            DECLARE @cos_phi FLOAT = COS(@phi), @sin_phi FLOAT = SIN(@phi);
            DECLARE @dx FLOAT = (@cx-@nx)/2.0, @dy FLOAT = (@cy-@ny)/2.0;
            DECLARE @x1p FLOAT =  @cos_phi*@dx + @sin_phi*@dy;
            DECLARE @y1p FLOAT = -@sin_phi*@dx + @cos_phi*@dy;

            --correct out-of-range radii (SVG B.2.5).
            DECLARE @rx_sq FLOAT=@rx*@rx, @ry_sq FLOAT=@ry*@ry;
            DECLARE @x1p_sq FLOAT=@x1p*@x1p, @y1p_sq FLOAT=@y1p*@y1p;
            DECLARE @lambda FLOAT = @x1p_sq/@rx_sq + @y1p_sq/@ry_sq;
            IF @lambda > 1
            BEGIN
                DECLARE @lam_sqrt FLOAT = SQRT(@lambda);
                SET @rx = @lam_sqrt*@rx; SET @ry = @lam_sqrt*@ry;
                SET @rx_sq=@rx*@rx; SET @ry_sq=@ry*@ry;
            END

            DECLARE @sign INT = CASE WHEN @fA<>@fS THEN 1 ELSE -1 END;
            DECLARE @num FLOAT = @rx_sq*@ry_sq - @rx_sq*@y1p_sq - @ry_sq*@x1p_sq;
            DECLARE @den FLOAT = @rx_sq*@y1p_sq + @ry_sq*@x1p_sq;
            DECLARE @sq  FLOAT = CASE WHEN @num/@den < 0 THEN 0
                                      ELSE SQRT(@num/@den) END;
            DECLARE @cxp FLOAT = @sign*@sq*(@rx*@y1p/@ry);
            DECLARE @cyp FLOAT = @sign*@sq*(-@ry*@x1p/@rx);

            DECLARE @acx FLOAT = @cos_phi*@cxp - @sin_phi*@cyp + (@cx+@nx)/2.0;
            DECLARE @acy FLOAT = @sin_phi*@cxp + @cos_phi*@cyp + (@cy+@ny)/2.0;

            DECLARE @theta1 FLOAT = ATN2((@y1p-@cyp)/@ry, (@x1p-@cxp)/@rx);
            DECLARE @dtheta FLOAT = ATN2((-@y1p-@cyp)/@ry, (-@x1p-@cxp)/@rx) - @theta1;
            IF @fS=0 AND @dtheta>0 SET @dtheta -= 2*PI();
            IF @fS=1 AND @dtheta<0 SET @dtheta += 2*PI();

            DECLARE @ang FLOAT, @arc_x FLOAT, @arc_y FLOAT, @arc_i INT = 1;
            WHILE @arc_i <= @flatten_steps
            BEGIN
                SET @ang = @theta1 + @dtheta * @arc_i / @flatten_steps;
                SET @arc_x = @cos_phi*@rx*COS(@ang) - @sin_phi*@ry*SIN(@ang) + @acx;
                SET @arc_y = @sin_phi*@rx*COS(@ang) + @cos_phi*@ry*SIN(@ang) + @acy;
                INSERT INTO @points (subpath_id, x, y) VALUES (@sub_id, @arc_x, @arc_y);
                SET @arc_i += 1;
            END

            SET @cx=@nx; SET @cy=@ny;
            SET @cubic_prev=0; SET @quad_prev=0;
            SET @i += 7; CONTINUE;
        END

        --unexpected token: advance and break if we made no progress.
        SET @i += 1;
        IF @i = @prev_i BREAK;
        SET @prev_i = @i;
    END

    RETURN;
END
GO


/*transform composer.  parses a `transform` attribute value (one or several
of translate / scale / rotate / matrix / skewX / skewY) into the single 2x3
affine matrix (a,b,c,d,e,f).  also used to combine an ancestor <g> chain:
concatenate outermost transform first, innermost last, in one call.
SVG 1.1 s7.6 - leftmost token is the outermost transform.*/
IF OBJECT_ID('dbo.fn_ParseSvgTransform') IS NOT NULL
    DROP FUNCTION dbo.fn_ParseSvgTransform;
GO

CREATE FUNCTION dbo.fn_ParseSvgTransform (@s VARCHAR(4000))
RETURNS @r TABLE (a FLOAT, b FLOAT, c FLOAT, d FLOAT, e FLOAT, f FLOAT)
AS
BEGIN
    -- Accumulator starts as the identity matrix.
    DECLARE @a FLOAT = 1, @b FLOAT = 0, @c FLOAT = 0,
            @d FLOAT = 1, @e FLOAT = 0, @f FLOAT = 0;

    IF @s IS NULL OR LTRIM(RTRIM(@s)) = ''
    BEGIN
        INSERT @r(a,b,c,d,e,f) VALUES(@a,@b,@c,@d,@e,@f);
        RETURN;
    END

    DECLARE @t VARCHAR(4000) =
        REPLACE(REPLACE(REPLACE(@s, CHAR(9),' '), CHAR(10),' '), CHAR(13),' ');
    DECLARE @len INT = LEN(@t);
    DECLARE @pos INT = 1;

    WHILE @pos <= @len
    BEGIN
        WHILE @pos <= @len AND SUBSTRING(@t, @pos, 1) NOT LIKE '[A-Za-z]'
            SET @pos += 1;
        IF @pos > @len BREAK;

        DECLARE @kw_start INT = @pos;
        WHILE @pos <= @len AND SUBSTRING(@t, @pos, 1) LIKE '[A-Za-z]'
            SET @pos += 1;
        DECLARE @kw VARCHAR(20) = SUBSTRING(@t, @kw_start, @pos - @kw_start);

        WHILE @pos <= @len AND SUBSTRING(@t, @pos, 1) <> '('
            SET @pos += 1;
        IF @pos > @len BREAK;
        SET @pos += 1;

        DECLARE @args_start INT = @pos;
        WHILE @pos <= @len AND SUBSTRING(@t, @pos, 1) <> ')'
            SET @pos += 1;
        IF @pos > @len BREAK;
        DECLARE @args VARCHAR(1000) =
            SUBSTRING(@t, @args_start, @pos - @args_start);
        SET @pos += 1;

        SET @args = REPLACE(@args, ',', ' ');
        WHILE CHARINDEX('  ', @args) > 0
            SET @args = REPLACE(@args, '  ', ' ');
        SET @args = LTRIM(RTRIM(@args));

        DECLARE @n1 FLOAT, @n2 FLOAT, @n3 FLOAT,
                @n4 FLOAT, @n5 FLOAT, @n6 FLOAT;
        SET @n1 = NULL; SET @n2 = NULL; SET @n3 = NULL;
        SET @n4 = NULL; SET @n5 = NULL; SET @n6 = NULL;

        DECLARE @num_idx INT = 0;
        DECLARE @rest VARCHAR(1000) = @args;
        DECLARE @sp INT;
        DECLARE @piece VARCHAR(60);
        WHILE LEN(@rest) > 0 AND @num_idx < 6
        BEGIN
            SET @sp = CHARINDEX(' ', @rest);
            IF @sp = 0
            BEGIN
                SET @piece = @rest;
                SET @rest = '';
            END
            ELSE
            BEGIN
                SET @piece = LEFT(@rest, @sp - 1);
                SET @rest  = SUBSTRING(@rest, @sp + 1, LEN(@rest));
            END
            SET @num_idx += 1;
            IF    @num_idx = 1 SET @n1 = TRY_CAST(@piece AS FLOAT);
            ELSE IF @num_idx = 2 SET @n2 = TRY_CAST(@piece AS FLOAT);
            ELSE IF @num_idx = 3 SET @n3 = TRY_CAST(@piece AS FLOAT);
            ELSE IF @num_idx = 4 SET @n4 = TRY_CAST(@piece AS FLOAT);
            ELSE IF @num_idx = 5 SET @n5 = TRY_CAST(@piece AS FLOAT);
            ELSE IF @num_idx = 6 SET @n6 = TRY_CAST(@piece AS FLOAT);
        END

        DECLARE @na FLOAT = 1, @nb FLOAT = 0, @nc FLOAT = 0,
                @nd FLOAT = 1, @ne FLOAT = 0, @nf FLOAT = 0;

        IF @kw COLLATE Latin1_General_CI_AS = 'translate'
        BEGIN
            SET @ne = ISNULL(@n1, 0);
            SET @nf = ISNULL(@n2, 0);
        END
        ELSE IF @kw COLLATE Latin1_General_CI_AS = 'scale'
        BEGIN
            SET @na = ISNULL(@n1, 1);
            SET @nd = ISNULL(@n2, @n1);
        END
        ELSE IF @kw COLLATE Latin1_General_CI_AS = 'rotate'
        BEGIN
            DECLARE @rad FLOAT = ISNULL(@n1, 0) * PI() / 180.0;
            DECLARE @co  FLOAT = COS(@rad);
            DECLARE @si  FLOAT = SIN(@rad);
            IF @n2 IS NOT NULL AND @n3 IS NOT NULL
            BEGIN
                --rotate(a, cx, cy) = translate(cx,cy) rotate(a) translate(-cx,-cy).
                SET @na = @co;  SET @nb = @si;
                SET @nc = -@si; SET @nd = @co;
                SET @ne = @n2 * (1 - @co) + @n3 * @si;
                SET @nf = @n3 * (1 - @co) - @n2 * @si;
            END
            ELSE
            BEGIN
                SET @na = @co;  SET @nb = @si;
                SET @nc = -@si; SET @nd = @co;
            END
        END
        ELSE IF @kw COLLATE Latin1_General_CI_AS = 'matrix'
        BEGIN
            SET @na = ISNULL(@n1, 1); SET @nb = ISNULL(@n2, 0);
            SET @nc = ISNULL(@n3, 0); SET @nd = ISNULL(@n4, 1);
            SET @ne = ISNULL(@n5, 0); SET @nf = ISNULL(@n6, 0);
        END
        ELSE IF @kw COLLATE Latin1_General_CI_AS = 'skewx'
        BEGIN
            SET @nc = TAN(ISNULL(@n1, 0) * PI() / 180.0);
        END
        ELSE IF @kw COLLATE Latin1_General_CI_AS = 'skewy'
        BEGIN
            SET @nb = TAN(ISNULL(@n1, 0) * PI() / 180.0);
        END
        --any other keyword falls through as identity.

        --acc := acc * this_matrix.
        DECLARE @ra FLOAT, @rb FLOAT, @rc FLOAT,
                @rd FLOAT, @re FLOAT, @rf FLOAT;
        SET @ra = @a * @na + @c * @nb;
        SET @rb = @b * @na + @d * @nb;
        SET @rc = @a * @nc + @c * @nd;
        SET @rd = @b * @nc + @d * @nd;
        SET @re = @a * @ne + @c * @nf + @e;
        SET @rf = @b * @ne + @d * @nf + @f;
        SET @a = @ra; SET @b = @rb; SET @c = @rc;
        SET @d = @rd; SET @e = @re; SET @f = @rf;
    END

    INSERT @r(a,b,c,d,e,f) VALUES(@a,@b,@c,@d,@e,@f);
    RETURN;
END
GO
