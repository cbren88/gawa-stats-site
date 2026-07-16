import json
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("NEON_DB_URL")
QUIZ_DATE    = os.getenv("QUIZ_DATE")  # e.g. "2026-07-02" for backfill; defaults to today

REPO     = Path(__file__).parent.parent
TEMPLATE = Path(__file__).parent / "template.html"
OUTPUT   = Path(__file__).parent / "index.html"
ARCHIVE  = Path(__file__).parent / "archive"


def select_clues(clues_obj: dict) -> list:
    """Pick 4 random non-initials clues then append initials last.
    Ensures 'More specifically' never appears without the broad position clue."""
    pool = []
    for bucket in ['identity', 'career', 'ni_record']:
        pool.extend([c for c in clues_obj.get(bucket, []) if c is not None])
    random.shuffle(pool)
    selected = pool[:4]

    has_more_spec = any(c.startswith('More specifically') for c in selected)
    has_broad_pos = any(c.startswith('I play as a') for c in selected)

    if has_more_spec and not has_broad_pos:
        broad_in_pool = [c for c in pool[4:] if c.startswith('I play as a')]
        if broad_in_pool:
            selected = [c for c in selected if not c.startswith('More specifically')]
            selected.append(broad_in_pool[0])
        else:
            selected = [c for c in selected if not c.startswith('More specifically')]

    selected.append(clues_obj['initials'])
    return selected


def main():
    if not DATABASE_URL:
        sys.exit("ERROR: Set DATABASE_URL or NEON_DB_URL first.")

    target_date = QUIZ_DATE or str(date.today())
    is_today    = (target_date == str(date.today()))

    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("SET search_path TO rpt, ctrl, stg, public")

        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    q.quiz_number,
                    q.question_type,
                    q.tm_player_id,
                    q.player_name,
                    q.clues,
                    q.fixture_info,
                    q.lineup_json,
                    q.missing_player,
                    q.missing_pitch_top,
                    q.missing_pitch_left,
                    q.source_fixture_id,
                    q.goalscorer_match_id,
                    q.goalscorer_data,
                    q.missing_tm_player_id,
                    q.missing_goal_sequence,
                    q.debut_tm_player_id,
                    q.debut_opponent,
                    q.debut_year,
                    q.debut_tm_match_id,
                    COALESCE(
                        p.transfermarkt_url,
                        CASE WHEN q.tm_player_id IS NOT NULL
                             THEN 'https://www.transfermarkt.co.uk/-/profil/spieler/' || q.tm_player_id
                        END
                    ) AS transfermarkt_url,
                    CASE WHEN q.source_fixture_id IS NOT NULL
                         THEN 'https://www.transfermarkt.co.uk/spielbericht/index/spielbericht/' || q.source_fixture_id
                    END AS match_url,
                    CASE WHEN q.goalscorer_match_id IS NOT NULL
                         THEN 'https://www.transfermarkt.co.uk/spielbericht/index/spielbericht/' || q.goalscorer_match_id
                    END AS goalscorer_match_url,
                    CASE WHEN q.debut_tm_match_id IS NOT NULL
                         THEN 'https://www.transfermarkt.co.uk/spielbericht/index/spielbericht/' || q.debut_tm_match_id
                    END AS debut_match_url
                FROM ctrl.quiz_questions q
                LEFT JOIN rpt.dim_player p ON p.tm_player_id = q.tm_player_id
                WHERE q.used_date = %s
            """, (target_date,))
            row = cur.fetchone()

        if not row:
            sys.exit(f"ERROR: No quiz question for {target_date}.")

        (quiz_number, question_type, tm_player_id, player_name,
         clues, fixture_info, lineup_json, missing_player,
         missing_pitch_top, missing_pitch_left, source_fixture_id,
         goalscorer_match_id, goalscorer_data, missing_tm_player_id, missing_goal_sequence,
         debut_tm_player_id, debut_opponent, debut_year, debut_tm_match_id,
         tm_url, match_url, goalscorer_match_url, debut_match_url) = row

        # Get prev/next quiz dates for navigation
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    MAX(used_date) FILTER (WHERE used_date < %s) AS prev_date,
                    MIN(used_date) FILTER (WHERE used_date > %s) AS next_date
                FROM ctrl.quiz_questions
                WHERE used_date IS NOT NULL
            """, (target_date, target_date))
            nav = cur.fetchone()

        prev_date = str(nav[0]) if nav[0] else None
        next_date = str(nav[1]) if nav[1] else None

        # Build quiz data object
        if question_type == 'who_am_i':
            quiz_data = {
                "quiz_number":       quiz_number,
                "question_type":     "who_am_i",
                "player_name":       player_name,
                "clues":             select_clues(clues),
                "transfermarkt_url": tm_url or "",
                "match_url":         "",
                "quiz_date":         target_date,
                "prev_date":         prev_date,
                "next_date":         next_date,
                "is_today":          is_today,
            }
        elif question_type == 'missing_goalscorer':
            # Look up the missing scorer's actual name and TM profile URL —
            # goalscorer_data has the name nulled out (never sent to the client
            # until solved), but we need it server-side for guess-checking
            # and for the post-game reveal links, same pattern as missing_lineup.
            # missing_tm_player_id is always an NI scorer (see generate_goalscorer_bank.sql).
            #
            # rpt.dim_player only covers SportAPI-sourced players (current/recent
            # squads with a richer profile) — historical players scraped only via
            # Transfermarkt (e.g. David Healy, retired before the SportAPI
            # integration existed) have no row there at all. Fall back to
            # stg.ni_fixture_players.player_name, which is guaranteed to have an
            # entry for anyone who appears in a scraped match, since that's the
            # actual source the name was captured from originally.
            missing_scorer_name = None
            missing_scorer_url  = None
            if missing_tm_player_id:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT full_name,
                               COALESCE(
                                   transfermarkt_url,
                                   'https://www.transfermarkt.co.uk/-/profil/spieler/' || %s
                               )
                        FROM rpt.dim_player
                        WHERE tm_player_id = %s
                    """, (missing_tm_player_id, missing_tm_player_id))
                    found = cur.fetchone()

                if not found:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT player_name
                            FROM stg.ni_fixture_players
                            WHERE tm_player_id = %s
                              AND player_name IS NOT NULL
                            ORDER BY LENGTH(player_name) DESC, scraped_at DESC
                            LIMIT 1
                        """, (missing_tm_player_id,))
                        fallback = cur.fetchone()
                    if fallback:
                        found = (
                            fallback[0],
                            'https://www.transfermarkt.co.uk/-/profil/spieler/' + missing_tm_player_id,
                        )

                if found:
                    missing_scorer_name, missing_scorer_url = found
                else:
                    missing_scorer_url = (
                        'https://www.transfermarkt.co.uk/-/profil/spieler/' + missing_tm_player_id
                    )

            quiz_data = {
                "quiz_number":            quiz_number,
                "question_type":          "missing_goalscorer",
                "player_name":            missing_scorer_name or "",
                "missing_tm_player_id":   missing_tm_player_id,
                "missing_goal_sequence":  missing_goal_sequence,
                "goalscorer_data":        goalscorer_data,
                "transfermarkt_url":      missing_scorer_url or "",
                "match_url":              goalscorer_match_url or "",
                "quiz_date":              target_date,
                "prev_date":              prev_date,
                "next_date":              next_date,
                "is_today":               is_today,
            }
        elif question_type == 'debut_details':
            # player_name is already populated directly on this row by
            # generate_debut_bank.sql, so no name-fallback lookup is needed
            # here — only the TM profile URL, since debut_tm_player_id is a
            # separate column from tm_player_id (used by who_am_i) and isn't
            # covered by the main query's transfermarkt_url join above.
            debut_scorer_url = None
            if debut_tm_player_id:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT transfermarkt_url FROM rpt.dim_player
                        WHERE tm_player_id = %s
                    """, (debut_tm_player_id,))
                    found = cur.fetchone()
                debut_scorer_url = (
                    found[0] if found and found[0]
                    else 'https://www.transfermarkt.co.uk/-/profil/spieler/' + debut_tm_player_id
                )

            quiz_data = {
                "quiz_number":        quiz_number,
                "question_type":      "debut_details",
                "player_name":        player_name,
                "debut_tm_player_id": debut_tm_player_id,
                "debut_opponent":     debut_opponent,
                "debut_year":         debut_year,
                "transfermarkt_url":  debut_scorer_url or "",
                "match_url":          debut_match_url or "",
                "quiz_date":          target_date,
                "prev_date":          prev_date,
                "next_date":          next_date,
                "is_today":           is_today,
            }
        else:
            quiz_data = {
                "quiz_number":        quiz_number,
                "question_type":      "missing_lineup",
                "player_name":        missing_player,
                "fixture_info":       fixture_info,
                "lineup_json":        lineup_json,
                "missing_pitch_top":  float(missing_pitch_top) if missing_pitch_top else None,
                "missing_pitch_left": float(missing_pitch_left) if missing_pitch_left else None,
                "transfermarkt_url":  tm_url or "",
                "match_url":          match_url or "",
                "quiz_date":          target_date,
                "prev_date":          prev_date,
                "next_date":          next_date,
                "is_today":           is_today,
            }

        # Label used in commit messages / log output — player_name is NULL
        # for missing_goalscorer rows in the raw query result, so use the
        # resolved scorer name (or fall back to the fixture id) instead
        if question_type == 'missing_goalscorer':
            log_label = missing_scorer_name or f"match {goalscorer_match_id}"
        elif question_type == 'missing_lineup':
            log_label = missing_player
        else:
            log_label = player_name

        # Player names for autocomplete
        # Filtering to names containing a space excludes surname-only entries
        # (e.g. "Cathcart", "McNair") that TM's match-sheet pages often show
        # without a first name — these aren't useful autocomplete suggestions
        # on their own, and a fuller name for the same player is normally
        # already present via one of the other two sources in this union.
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT full_name FROM rpt.dim_player
                WHERE senior_caps >= 1 AND full_name IS NOT NULL AND full_name LIKE '% %'

                UNION

                SELECT DISTINCT player_name FROM stg.ni_lineup_positions
                WHERE ni_side = TRUE AND player_name IS NOT NULL AND player_name LIKE '% %'

                UNION

                SELECT DISTINCT player_name FROM stg.ni_fixture_players
                WHERE ni_side = TRUE AND player_name IS NOT NULL AND player_name LIKE '% %'

                ORDER BY 1
            """)
            player_names = [r[0] for r in cur.fetchall()]

        # Opponent/team names for the debut_details autocomplete — every
        # distinct national team NI have faced, excluding NI themselves.
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT team FROM (
                    SELECT home_team AS team FROM stg.ni_fixtures
                    UNION
                    SELECT away_team AS team FROM stg.ni_fixtures
                ) t
                WHERE team IS NOT NULL AND LOWER(team) NOT LIKE '%northern ireland%'
                ORDER BY 1
            """)
            team_names = [r[0] for r in cur.fetchall()]

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__QUIZ_DATA__",    json.dumps(quiz_data,    ensure_ascii=False))
    html = html.replace("__PLAYER_NAMES__", json.dumps(player_names, ensure_ascii=False))
    html = html.replace("__TEAM_NAMES__",   json.dumps(team_names,   ensure_ascii=False))

    # Always save to archive
    ARCHIVE.mkdir(exist_ok=True)
    archive_file = ARCHIVE / f"{target_date}.html"
    archive_file.write_text(html, encoding="utf-8")
    print(f"✓ Saved archive: {archive_file}")

    # Only overwrite index.html if building today's quiz
    if is_today:
        OUTPUT.write_text(html, encoding="utf-8")
        print(f"✓ Built Quiz #{quiz_number} — {question_type} — {log_label}")
        print(f"  Output: {OUTPUT}")

    print(f"  Players in autocomplete: {len(player_names)}")
    print(f"  Teams in autocomplete: {len(team_names)}")

    if is_today:
        result = os.system(
            f'cd "{REPO}" && '
            f'git add quiz/index.html quiz/archive/ && '
            f'git commit -m "Quiz #{quiz_number} — {question_type} — {log_label}" && '
            f'git push'
        )
        if result == 0:
            print("✓ Pushed to GitHub — Cloudflare Pages deploying")
        else:
            print("⚠ Git push failed — check your GitHub credentials")
    else:
        # For backfill, just commit the archive file
        result = os.system(
            f'cd "{REPO}" && '
            f'git add quiz/archive/{target_date}.html && '
            f'git commit -m "Archive Quiz #{quiz_number} — {target_date}" && '
            f'git push'
        )
        if result == 0:
            print(f"✓ Archive pushed for {target_date}")
        else:
            print("⚠ Git push failed")


if __name__ == "__main__":
    main()
