INSERT INTO ctrl.quiz_questions (
    question_type, player_name, tm_player_id, clues,
    source_fixture_id, fixture_info, lineup_json,
    missing_player, missing_pitch_top, missing_pitch_left
)
WITH eligible_fixtures AS (
    SELECT l.tm_match_id
    FROM stg.ni_lineup_positions l
    WHERE l.ni_side = TRUE
      AND l.appearance_type = 'started'
      AND l.pitch_top IS NOT NULL
      AND l.pitch_left IS NOT NULL
    GROUP BY l.tm_match_id
    HAVING COUNT(*) = 11
),
unused_fixtures AS (
    SELECT ef.tm_match_id
    FROM eligible_fixtures ef
    WHERE NOT EXISTS (
        SELECT 1 FROM ctrl.quiz_questions q
        WHERE q.question_type = 'missing_lineup'
          AND q.source_fixture_id = ef.tm_match_id
    )
),
fixture_pool AS (
    SELECT
        uf.tm_match_id,
        f.match_date,
        f.home_team,
        f.away_team,
        f.home_score,
        f.away_score,
        f.competition
    FROM unused_fixtures uf
    JOIN stg.ni_fixtures f ON f.tm_match_id = uf.tm_match_id
    ORDER BY random()
    LIMIT 10
),
fixture_missing AS (
    SELECT DISTINCT ON (fp.tm_match_id)
        fp.tm_match_id,
        fp.match_date,
        fp.home_team,
        fp.away_team,
        fp.home_score,
        fp.away_score,
        fp.competition,
        l.player_name  AS missing_player,
        l.tm_player_id AS missing_player_id,
        l.pitch_top    AS missing_pitch_top,
        l.pitch_left   AS missing_pitch_left
    FROM fixture_pool fp
    JOIN stg.ni_lineup_positions l
      ON l.tm_match_id = fp.tm_match_id
     AND l.ni_side = TRUE
     AND l.appearance_type = 'started'
    ORDER BY fp.tm_match_id, random()
),
lineup_data AS (
    SELECT
        fm.tm_match_id,
        jsonb_agg(
            jsonb_build_object(
                'name', l.player_name,
                'top',  l.pitch_top,
                'left', l.pitch_left
            )
        ) AS lineup_json
    FROM fixture_missing fm
    JOIN stg.ni_lineup_positions l
      ON l.tm_match_id = fm.tm_match_id
     AND l.ni_side = TRUE
     AND l.appearance_type = 'started'
     AND l.tm_player_id <> fm.missing_player_id
    GROUP BY fm.tm_match_id
)
SELECT
    'missing_lineup',
    fm.missing_player,
    fm.missing_player_id,
    NULL,
    fm.tm_match_id,
    jsonb_build_object(
        'match_date',  fm.match_date,
        'home_team',   fm.home_team,
        'away_team',   fm.away_team,
        'home_score',  fm.home_score,
        'away_score',  fm.away_score,
        'competition', fm.competition
    ),
    ld.lineup_json,
    fm.missing_player,
    fm.missing_pitch_top,
    fm.missing_pitch_left
FROM fixture_missing fm
JOIN lineup_data ld ON ld.tm_match_id = fm.tm_match_id
ON CONFLICT DO NOTHING;