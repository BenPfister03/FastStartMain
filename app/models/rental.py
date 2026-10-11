from datetime import date, timedelta
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.listing import Listing
    from app.models.payment import Payment

RENTAL_DAYS = 7          # days allowed before a rental is late
LATE_FEE_PER_DAY = 2.0


class Rental(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id")
    renter_id: int = Field(foreign_key="customer.id")
    rental_date: date
    return_date: Optional[date] = None

    listing: Optional["Listing"] = Relationship(back_populates="rentals")
    renter: Optional["Customer"] = Relationship(back_populates="rentals")
    payments: List["Payment"] = Relationship(back_populates="rental")

    def late_fee(self, on: date) -> float:
        days_late = (on - (self.rental_date + timedelta(days=RENTAL_DAYS))).days
        return max(0, days_late) * LATE_FEE_PER_DAY

    def amount_due(self, on: date) -> float:
        return self.listing.price + self.late_fee(on)

    def __str__(self) -> str:
        status = f"returned {self.return_date}" if self.return_date else "out"
        return f"(Rental id={self.id}, game={self.listing.game.title}, rented {self.rental_date}, {status})"
