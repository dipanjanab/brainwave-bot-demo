from contextlib import closing
# pyrefly: ignore [missing-import]
from app.database.connection import connect


CREATE_STORIES_TABLE = """
CREATE TABLE IF NOT EXISTS stories (
    story_id INTEGER PRIMARY KEY,
    story_title TEXT NOT NULL,
    market TEXT NOT NULL CHECK (market IN ('EMIA', 'APAC', 'AMER', 'LATAM')),
    category TEXT NOT NULL,
    submission_date TEXT NOT NULL,
    status TEXT NOT NULL,
    submitter TEXT NOT NULL,
    revenue REAL NOT NULL CHECK (revenue >= 0)
)
"""


def create_database() -> None:
    with closing(connect()) as connection:
        connection.execute(CREATE_STORIES_TABLE)
        table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'stories'"
        ).fetchone()[0]
        if "EMIA" in table_sql:
            connection.execute("ALTER TABLE stories RENAME TO stories_legacy")
            connection.execute(CREATE_STORIES_TABLE)
            connection.execute(
                """INSERT INTO stories
                (story_id, story_title, market, category, submission_date, status, submitter, revenue)
                SELECT story_id, story_title,
                    CASE WHEN market = 'NEMIA' THEN 'EMIA' ELSE market END,
                    category, submission_date, status, submitter, revenue
                FROM stories_legacy"""
            )
            connection.execute("DROP TABLE stories_legacy")
        connection.commit()


if __name__ == "__main__":
    create_database()
    print("Brainwave database created.")
