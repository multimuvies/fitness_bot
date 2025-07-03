"""models_and_db.py — схема БД + удобный геттер сессии
    ▸ добавлены таблицы FriendRequest и Friend
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlmodel import Field, SQLModel, Session, create_engine

# ──────────────────── конфиг SQLite ────────────────────
DB_PATH = Path(__file__).with_name("fitness.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)   # echo=True для отладки


# ─────────────────────── MODELS ────────────────────────
# models_and_db.py ─ добавить поле
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    chat_id: int = Field(unique=True, index=True)
    username: Optional[str] = Field(default=None, index=True)   # ← НОВОЕ
    age: int
    height_cm: int
    weight_kg: float
    gender: str
    bmi: float
    tdee: int



class Workout(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    raw_text: str
    type: str
    duration_min: int
    calories: int                            # всегда <0
    method: str                              # gpt|fallback|user


class Meal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    raw_text: str
    description: str
    calories: int                            # всегда >0


class Weight(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    weight_kg: float
    bmi: Optional[float] = None              # nullable, чтобы не падало на NULL


class Checkpoint(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ──────────────── NEW: друзья ────────────────
class FriendRequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    from_id: int = Field(foreign_key="user.id")
    to_id: int = Field(foreign_key="user.id")
    status: str = Field(default="pending")   # pending / accepted / declined
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Friend(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    friend_id: int = Field(foreign_key="user.id")


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
