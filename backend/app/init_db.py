
from app import models  # Registers all database models.
from app.db import Base, engine


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized successfully.")


if __name__ == "__main__":
    initialize_database()
