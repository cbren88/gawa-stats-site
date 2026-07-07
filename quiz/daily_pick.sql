-- =============================================================================
-- GAWA QUIZ — Daily pick
-- Run once daily (1am cron). Rotates strictly between the three question
-- types based on yesterday's type, then picks a random unused question
-- of that type.
-- =============================================================================

WITH yesterday_type AS (
    SELECT question_type
    FROM ctrl.quiz_questions
    WHERE used_date = CURRENT_DATE - INTERVAL '1 day'
    LIMIT 1
),
next_type AS (
    -- Rotation order: who_am_i -> missing_lineup -> missing_goalscorer -> repeat
    SELECT CASE (SELECT question_type FROM yesterday_type)
        WHEN 'who_am_i'           THEN 'missing_lineup'
        WHEN 'missing_lineup'     THEN 'missing_goalscorer'
        WHEN 'missing_goalscorer' THEN 'who_am_i'
        ELSE 'who_am_i'  -- first-ever run, no prior quiz
    END AS question_type
),
-- Availability check: does the rotated-to type actually have unused rows?
type_available AS (
    SELECT EXISTS (
        SELECT 1
        FROM ctrl.quiz_questions q
        JOIN next_type nt ON nt.question_type = q.question_type
        WHERE q.used_date IS NULL
    ) AS is_available
),
-- Fallback if the rotated-to type is empty: pick randomly from whichever
-- type(s) still have unused rows
fallback_type AS (
    SELECT q.question_type
    FROM ctrl.quiz_questions q
    WHERE q.used_date IS NULL
    GROUP BY q.question_type
    ORDER BY random()
    LIMIT 1
),
resolved_type AS (
    SELECT CASE
        WHEN (SELECT is_available FROM type_available) THEN (SELECT question_type FROM next_type)
        ELSE (SELECT question_type FROM fallback_type)
    END AS question_type
),
pick AS (
    SELECT q.quiz_question_id
    FROM ctrl.quiz_questions q
    JOIN resolved_type rt ON rt.question_type = q.question_type
    WHERE q.used_date IS NULL
    ORDER BY random()
    LIMIT 1
)
UPDATE ctrl.quiz_questions
SET
    used_date   = CURRENT_DATE,
    quiz_number = COALESCE(
                      (SELECT MAX(quiz_number) FROM ctrl.quiz_questions WHERE quiz_number IS NOT NULL),
                      0
                  ) + 1
WHERE quiz_question_id IN (SELECT quiz_question_id FROM pick)
  AND NOT EXISTS (
      SELECT 1 FROM ctrl.quiz_questions WHERE used_date = CURRENT_DATE
  );
