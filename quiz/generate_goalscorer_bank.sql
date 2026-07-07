-- =============================================================================
-- GAWA QUIZ — Generate missing_goalscorer questions
-- Run weekly to top up the bank (adds up to 10 new questions per run)
-- Requires: stg.ni_fixture_goals to be populated (via refresh_ni_fixtures.py)
-- =============================================================================

INSERT INTO ctrl.quiz_questions (
    question_type, fixture_info,
    goalscorer_match_id, goalscorer_data, missing_tm_player_id
)
WITH eligible_fixtures AS (
    -- Fixtures with at least 1 NI goal (own goals excluded)
    SELECT DISTINCT g.tm_match_id
    FROM stg.ni_fixture_goals g
    JOIN stg.ni_fixture_players p
         ON p.tm_match_id = g.tm_match_id
        AND p.tm_player_id = g.tm_player_id
    WHERE p.ni_side = TRUE
      AND g.is_own_goal = FALSE
),
unused_fixtures AS (
    -- Exclude fixtures already in the question bank
    SELECT ef.tm_match_id
    FROM eligible_fixtures ef
    WHERE NOT EXISTS (
        SELECT 1 FROM ctrl.quiz_questions q
        WHERE q.question_type = 'missing_goalscorer'
          AND q.goalscorer_match_id = ef.tm_match_id
    )
),
fixture_pool AS (
    -- Pick up to 10 unused fixtures at random
    SELECT uf.tm_match_id
    FROM unused_fixtures uf
    ORDER BY random()
    LIMIT 10
),
-- All non-own-goal goals per pooled fixture, in chronological order,
-- with a random NI goal chosen per fixture to blank
goal_rows AS (
    SELECT
        fp.tm_match_id,
        g.tm_player_id,
        p.player_name,
        p.ni_side,
        g.goal_minute,
        g.goal_sequence
    FROM fixture_pool fp
    JOIN stg.ni_fixture_goals g ON g.tm_match_id = fp.tm_match_id
    JOIN stg.ni_fixture_players p
         ON p.tm_match_id = g.tm_match_id
        AND p.tm_player_id = g.tm_player_id
    WHERE g.is_own_goal = FALSE
),
missing_pick AS (
    -- One random NI goal per fixture to be the blanked answer
    SELECT DISTINCT ON (tm_match_id)
        tm_match_id,
        tm_player_id AS missing_tm_player_id
    FROM goal_rows
    WHERE ni_side = TRUE
    ORDER BY tm_match_id, random()
),
fixture_meta AS (
    SELECT
        fp.tm_match_id,
        f.match_date,
        f.home_team,
        f.away_team,
        f.home_score,
        f.away_score,
        f.competition
    FROM fixture_pool fp
    JOIN stg.ni_fixtures f ON f.tm_match_id = fp.tm_match_id
)
SELECT
    'missing_goalscorer' AS question_type,
    jsonb_build_object(
        'match_date',   fm.match_date,
        'home_team',    fm.home_team,
        'away_team',    fm.away_team,
        'home_score',   fm.home_score,
        'away_score',   fm.away_score,
        'competition',  fm.competition
    ) AS fixture_info,
    fm.tm_match_id AS goalscorer_match_id,
    jsonb_build_object(
        'match_date',    fm.match_date,
        'home_team',     fm.home_team,
        'away_team',     fm.away_team,
        'home_score',    fm.home_score,
        'away_score',    fm.away_score,
        'ni_goals', (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'tm_player_id', gr.tm_player_id,
                    'player_name',
                        CASE WHEN gr.tm_player_id = mp.missing_tm_player_id
                             THEN NULL
                             ELSE gr.player_name
                        END,
                    'minute', gr.goal_minute
                ) ORDER BY gr.goal_sequence
            )
            FROM goal_rows gr
            WHERE gr.tm_match_id = fm.tm_match_id AND gr.ni_side = TRUE
        ),
        'opponent_goals', (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'player_name', gr.player_name,
                    'minute', gr.goal_minute
                ) ORDER BY gr.goal_sequence
            )
            FROM goal_rows gr
            WHERE gr.tm_match_id = fm.tm_match_id AND gr.ni_side = FALSE
        )
    ) AS goalscorer_data,
    mp.missing_tm_player_id
FROM fixture_meta fm
JOIN missing_pick mp ON mp.tm_match_id = fm.tm_match_id;
