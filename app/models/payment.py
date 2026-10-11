from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.rental import Rental


class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    rental_id: Optional[int] = Field(default=None, foreign_key="rental.id")  # None = joining deposit
    customer_id: int = Field(foreign_key="customer.id")
    payment_date: date
    amount: float

    customer: Optional["Customer"] = Relationship(back_populates="payments")
    rental: Optional["Rental"] = Relationship(back_populates="payments")

    def __str__(self) -> str:
        return f"(Payment id={self.id}, amount={self.amount:.2f}, date={self.payment_date})"
