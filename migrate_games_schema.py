from sqlalchemy import text

from app.db.database import engine


def migrate_games_schema():
    with engine.begin() as connection:
        table_exists = connection.execute(
            text("SELECT to_regclass('public.games')")
        ).scalar()

        if table_exists is None:
            print("Table public.games does not exist yet. Nothing to migrate.")
            return

        connection.execute(text("DROP INDEX IF EXISTS ix_games_game_id"))
        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_games_game_id_team_id
                ON games (game_id, team_id)
                """
            )
        )

    print("Updated games uniqueness to (game_id, team_id).")


if __name__ == "__main__":
    migrate_games_schema()
