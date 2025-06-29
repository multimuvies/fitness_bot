# models_and_db.py — схема БД + удобный геттер сессии

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlmodel import Field, SQLModel, Session, create_engine

# ──────────────────── конфиг SQLite ────────────────────
DB_PATH = Path(__file__).with_name("fitness.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)  # echo=True для отладки


# ─────────────────────── MODELS ────────────────────────
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    chat_id: int = Field(unique=True, index=True)
    age: int
    height_cm: int
    weight_kg: float
    gender: str  # "male" / "female"
    bmi: float
    tdee: int


class Workout(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    raw_text: str
    type: str
    duration_min: int
    calories: int          # всегда <0
    method: str            # gpt|fallback|user


class Meal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    raw_text: str
    description: str
    calories: int          # всегда >0


class Weight(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    weight_kg: float
    bmi: Optional[float] = None   # ← делаем nullable, чтобы не падало на NULL


class Checkpoint(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ────────────────── init + helper ───────────────────
def init_db() -> None:
    """Создаёт таблицы, если их ещё нет."""
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Session:
    """Контекстный менеджер для работы с БД."""
    with Session(engine) as session:
        yield session


# при первом импорте создаём таблицы
init_db()
