"""Game-rental API routes for COMP3605 Tutorial 4."""
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.config import get_settings
from app.dependencies.session import SessionDep
from app.models import Game, Listing, Payment, Rental, User
from app.repositories.user import UserRepository
from app.services.auth_service import AuthService
from app.utilities.security import encrypt_password
from . import api_router


class SignupBody(BaseModel):
    username: str
    email: str
    password: str

class AuthBody(BaseModel):
    username: str
    password: str

class ListingBody(BaseModel):
    game_id: int
    condition: str
    price: float = PydanticField(gt=0)

class GameBody(BaseModel):
    title: str
    platform: str
    genre: str = ""
    release_year: int | None = None

class PaymentBody(BaseModel):
    amount: float = PydanticField(gt=0)

class RentalBody(BaseModel):
    listing_id: int
    customer_id: int

class ReturnBody(BaseModel):
    payment_id: int | None = None
    payment: float | None = PydanticField(default=None, gt=0)


def current_user(request: Request, db: Session) -> User:
    token = request.cookies.get("access_token")
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[get_settings().jwt_algorithm])
        user_id = int(payload.get("sub", ""))
    except (InvalidTokenError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_staff(request: Request, db: Session) -> User:
    user = current_user(request, db)
    if user.role not in {"admin", "staff"}:
        raise HTTPException(status_code=403, detail="Staff access required")
    return user


@api_router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(body: SignupBody, db: SessionDep):
    if db.exec(select(User).where((User.username == body.username) | (User.email == body.email))).first():
        raise HTTPException(status_code=400, detail="Username or email already exists")
    user = AuthService(UserRepository(db)).register_user(body.username, body.email, body.password)
    return {"id": user.id, "username": user.username, "email": user.email}


@api_router.post("/auth")
def authenticate(body: AuthBody, db: SessionDep):
    token = AuthService(UserRepository(db)).authenticate_user(body.username, body.password)
    if not token:
        raise HTTPException(status_code=400, detail="Invalid username or password")
    return {"access_token": token, "token_type": "bearer"}


@api_router.post("/games", status_code=status.HTTP_201_CREATED)
def create_game(body: GameBody, request: Request, db: SessionDep):
    require_staff(request, db)
    platform = body.platform.upper()
    if platform not in {"NSW", "PS5", "XBOX", "PC"}:
        raise HTTPException(status_code=422, detail="platform must be NSW, PS5, XBOX, or PC")
    game = Game(title=body.title, platform=platform, genre=body.genre, release_year=body.release_year)
    db.add(game); db.commit(); db.refresh(game)
    return game


@api_router.post("/listings", status_code=status.HTTP_201_CREATED)
def create_listing(body: ListingBody, request: Request, db: SessionDep):
    user = current_user(request, db)
    if user.role not in {"regular_user", "customer", "admin", "staff"}:
        raise HTTPException(status_code=403, detail="Customer access required")
    if not db.get(Game, body.game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    listing = Listing(game_id=body.game_id, owner_id=user.id, condition=body.condition, price=body.price)
    db.add(listing); db.commit(); db.refresh(listing)
    return listing


@api_router.get("/listings")
def get_listings(db: SessionDep, platform: str | None = None):
    query = select(Listing).where(Listing.status == "available")
    if platform:
        normalized = platform.upper()
        if normalized not in {"NSW", "PS5", "XBOX", "PC"}:
            raise HTTPException(status_code=422, detail="platform must be NSW, PS5, XBOX, or PC")
        query = query.join(Game, Listing.game_id == Game.id).where(Game.platform == normalized)
    listings = db.exec(query).all()
    result = []
    for listing in listings:
        game = db.get(Game, listing.game_id)
        result.append({"id": listing.id, "game_id": listing.game_id, "owner_id": listing.owner_id,
                       "condition": listing.condition, "price": listing.price, "status": listing.status,
                       "game": game.model_dump() if game else None})
    return result


@api_router.post("/payment", status_code=status.HTTP_201_CREATED)
def create_payment(body: PaymentBody, request: Request, db: SessionDep):
    staff = require_staff(request, db)
    payment = Payment(amount=body.amount, customer_id=staff.id)
    db.add(payment); db.commit(); db.refresh(payment)
    return {"paymentId": payment.id, "amount": payment.amount}


@api_router.post("/rentals", status_code=status.HTTP_201_CREATED)
def create_rental(body: RentalBody, request: Request, db: SessionDep):
    require_staff(request, db)
    listing = db.get(Listing, body.listing_id)
    customer = db.get(User, body.customer_id)
    if listing is None or listing.status != "available":
        raise HTTPException(status_code=404, detail="Available listing not found")
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    rental = Rental(listing_id=listing.id, customer_id=customer.id)
    listing.status = "rented"
    db.add(rental); db.add(listing); db.commit(); db.refresh(rental)
    return rental


@api_router.put("/rentals/{rental_id}", status_code=status.HTTP_201_CREATED)
def return_rental(rental_id: int, body: ReturnBody, request: Request, db: SessionDep):
    require_staff(request, db)
    rental = db.get(Rental, rental_id)
    if rental is None:
        raise HTTPException(status_code=404, detail="Rental not found")
    if rental.status == "returned":
        raise HTTPException(status_code=400, detail="Rental already returned")
    payment_id = body.payment_id
    if payment_id is None and body.payment is not None:
        payment = Payment(amount=body.payment, customer_id=rental.customer_id, purpose="rental_return")
        db.add(payment); db.commit(); db.refresh(payment)
        payment_id = payment.id
    if payment_id is not None and db.get(Payment, payment_id) is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    listing = db.get(Listing, rental.listing_id)
    if listing is not None:
        listing.status = "available"
        db.add(listing)
    rental.status = "returned"
    rental.payment_id = payment_id
    db.add(rental); db.commit(); db.refresh(rental)
    return rental


@api_router.post("/listings/{listing_id}/sell", status_code=status.HTTP_201_CREATED)
def sell_listing(listing_id: int, request: Request, db: SessionDep):
    user = current_user(request, db)
    listing = db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.owner_id != user.id:
        raise HTTPException(status_code=403, detail="You can only sell your own listing")
    if listing.status != "available":
        raise HTTPException(status_code=400, detail="Only available listings can be sold")
    listing.status = "sold"
    db.add(listing); db.commit(); db.refresh(listing)
    return {"message": "Listing marked as sold", "listing_id": listing.id, "status": listing.status}
