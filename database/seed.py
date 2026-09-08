from contextlib import closing
# pyrefly: ignore [missing-import]
from app.database.connection import connect
# pyrefly: ignore [missing-import]
from app.database.schema import create_database


STORIES = [
    ("AI Transformation", "EMIA", "AI", "2025-05-10", "Submitted", "John", 150000),
    ("Cloud Migration", "EMIA", "Cloud", "2025-07-15", "Submitted", "Sarah", 250000),
    ("Data Modernization", "APAC", "Data", "2025-08-20", "Submitted", "David", 180000),
    ("GenAI Assistant", "EMIA", "GenAI", "2026-02-10", "Submitted", "Emma", 320000),
    ("Retail Analytics", "APAC", "Analytics", "2026-06-12", "Submitted", "Alex", 210000),
    ("Supply-chain Vision", "AMER", "AI", "2026-04-22", "Submitted", "Priya", 400000),
    ("Contact Centre Copilot", "EMIA", "GenAI", "2026-08-03", "Draft", "Mina", 95000),
    ("Banking Lakehouse", "EMIA", "Data", "2026-08-28", "Submitted", "Omar", 275000),
    ("Commerce Platform", "LATAM", "Cloud", "2025-12-01", "Submitted", "Luis", 135000),
]


def seed_database() -> None:
    create_database()
    with closing(connect()) as connection:
        existing = connection.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
        if existing:
            return
        connection.executemany(
            """INSERT INTO stories
            (story_title, market, category, submission_date, status, submitter, revenue)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            STORIES,
        )
        connection.commit()


if __name__ == "__main__":
    seed_database()
    print("Sample Brainwave data inserted.")
