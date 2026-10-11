from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.listing import Listing


class Game(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str

    listings: List["Listing"] = Relationship(back_populates="game")

    def __str__(self) -> str:
        return f"(Game id={self.id}, title={self.title})"
