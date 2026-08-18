"""Create the Day 3 PostgreSQL tables in the configured database."""

from backend.database import DatabaseConfigurationError, initialize_database


def main() -> None:
    try:
        initialize_database()
    except DatabaseConfigurationError as exc:
        raise SystemExit(f"Database configuration error: {exc}") from exc
    print("Database initialized: projects and papers tables are ready.")


if __name__ == "__main__":
    main()
