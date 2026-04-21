import psycopg2
from airflow.hooks.base import BaseHook

UPSERT_MATCHES_SQL = """
    INSERT INTO bluewings_nest.matches (match_date, match_time, home_team, away_team,
                         home_score, away_score, stadium, competition,
                         season, match_day, status, updated_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT (match_date, home_team, away_team)
    DO UPDATE SET
        match_time = EXCLUDED.match_time,
        home_score = EXCLUDED.home_score,
        away_score = EXCLUDED.away_score,
        stadium = EXCLUDED.stadium,
        match_day = EXCLUDED.match_day,
        status = EXCLUDED.status,
        updated_at = NOW()
"""


def get_supabase_connection():
    conn = BaseHook.get_connection("supabase_postgres")
    conn_str = (
        f"host={conn.host} port={conn.port} dbname={conn.schema} "
        f"user={conn.login} password={conn.password} sslmode=require"
    )
    return psycopg2.connect(conn_str)


def upsert_matches(matches):
    if not matches:
        print("No matches to upsert")
        return 0

    pg_conn = get_supabase_connection()
    cursor = pg_conn.cursor()

    count = 0
    for m in matches:
        cursor.execute(UPSERT_MATCHES_SQL, (
            m["match_date"], m["match_time"], m["home_team"], m["away_team"],
            m["home_score"], m["away_score"], m["stadium"], m["competition"],
            m["season"], m["match_day"], m["status"],
        ))
        count += 1

    pg_conn.commit()
    cursor.close()
    pg_conn.close()
    print(f"Upserted {count} matches to Supabase")
    return count
