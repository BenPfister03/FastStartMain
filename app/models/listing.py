from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.game import Game
    from app.models.rental import Rental


class Availability(str, Enum):
    AVAILABLE = "available"
    RENTED = "rented"


class Listing(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id")
    owner_id: int = Field(foreign_key="customer.id")
    condition: str
    availability: Availability = Field(default=Availability.AVAILABLE)
    price: float

    game: Optional["Game"] = Relationship(back_populates="listings")
    owner: Optional["Customer"] = Relationship(back_populates="listings")
    rentals: List["Rental"] = Relationship(back_populates="listing")

    def __str__(self) -> str:
        return (f"(Listing id={self.id}, game={self.game.title}, condition={self.condition}, "
                f"price={self.price:.2f}, {self.availability.value})")
