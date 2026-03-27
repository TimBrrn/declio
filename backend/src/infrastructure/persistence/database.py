from sqlmodel import Session, SQLModel, create_engine

from backend.src.infrastructure.config.settings import settings

engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    import backend.src.infrastructure.persistence.models  # noqa: F401 — register tables

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
