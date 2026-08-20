"""Create the current PostgreSQL tables in the configured database."""

from backend.database import DatabaseConfigurationError, initialize_database


def main() -> None:
    try:
        initialize_database()
    except DatabaseConfigurationError as exc:
        raise SystemExit(f"Database configuration error: {exc}") from exc
    print("Database initialized: projects, papers, and paper_documents tables are ready.")


if __name__ == "__main__":
    main()
