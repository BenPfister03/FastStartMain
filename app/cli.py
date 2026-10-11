from typing import Annotated

import typer
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.database import create_db_and_tables, drop_all, get_cli_session
from app.models import Availability, Game, Listing, Rental
from app.services.customer_service import DEPOSIT, CustomerService

cli = typer.Typer(help="Peer-to-peer game rental CLI")

Username = Annotated[str, typer.Argument(help="Your username")]
Password = Annotated[str, typer.Argument(help="Your password")]


def _login(db, username: str, password: str):
    customer = CustomerService(db).authenticate(username, password)
    if not customer:
        print("Invalid username or password.")
        raise typer.Exit(1)
    return customer


@cli.command()
def initialize():
    """Drop and recreate all tables, then add a few sample games."""
    with get_cli_session() as db:
        drop_all()
        create_db_and_tables()
        for title in ["Zelda: Breath of the Wild", "Mario Kart 8", "FIFA 24"]:
            db.add(Game(title=title))
        db.commit()
        print("Database Initialized")


@cli.command()
def register(
    username: Annotated[str, typer.Argument(help="Unique username")],
    email: Annotated[str, typer.Argument(help="Unique email address")],
    password: Annotated[str, typer.Argument(help="Account password")],
):
    """Join the store as a customer (records the joining deposit)."""
    with get_cli_session() as db:
        try:
            customer = CustomerService(db).register(username, email, password)
        except IntegrityError:
            db.rollback()
            print("Username or email already taken!")
            raise typer.Exit(1)
        print(f"Welcome {customer.username}! Deposit of {DEPOSIT:.2f} recorded.")


@cli.command()
def add_game(title: Annotated[str, typer.Argument(help="Title of the game")]):
    """Add a game title to the catalogue."""
    with get_cli_session() as db:
        game = Game(title=title)
        db.add(game)
        db.commit()
        db.refresh(game)
        print(f"Added {game}")


@cli.command()
def catalogue():
    """View the game catalogue with every currently available listing."""
    with get_cli_session() as db:
        for game in db.exec(select(Game)).all():
            print(f"[{game.id}] {game.title}")
            for listing in game.listings:
                if listing.availability == Availability.AVAILABLE:
                    print(f"    listing #{listing.id}: {listing.condition}, "
                          f"{listing.price:.2f}, owner {listing.owner.username}")


@cli.command()
def list_game(
    username: Username,
    password: Password,
    game_id: Annotated[int, typer.Argument(help="ID of the game you are listing")],
    condition: Annotated[str, typer.Argument(help="Condition of your copy, e.g. Good")],
    price: Annotated[float, typer.Argument(help="Rental price")],
):
    """List a copy of a game you own for rental."""
    with get_cli_session() as db:
        customer = _login(db, username, password)
        game = db.get(Game, game_id)
        if not game:
            print(f"Game {game_id} not found!")
            raise typer.Exit(1)
        print(f"Listed: {customer.list_game(game, condition, price)}")


@cli.command()
def rent(
    username: Username,
    password: Password,
    listing_id: Annotated[int, typer.Argument(help="ID of the listing to rent")],
):
    """Rent an available listing."""
    with get_cli_session() as db:
        customer = _login(db, username, password)
        listing = db.get(Listing, listing_id)
        if not listing:
            print(f"Listing {listing_id} not found!")
            raise typer.Exit(1)
        try:
            rental = customer.rent_game(listing)
        except ValueError as e:
            print(e)
            raise typer.Exit(1)
        print(f"Rented: {rental}")


@cli.command()
def my_rentals(username: Username, password: Password):
    """Show your rentals and the amount due on each unreturned one."""
    from datetime import date
    with get_cli_session() as db:
        customer = _login(db, username, password)
        if not customer.rentals:
            print("No rentals found")
        for rental in customer.rentals:
            due = "" if rental.return_date else f" - due {rental.amount_due(date.today()):.2f}"
            print(f"{rental}{due}")


@cli.command()
def return_game(
    username: Username,
    password: Password,
    rental_id: Annotated[int, typer.Argument(help="ID of the rental being returned")],
    amount: Annotated[float, typer.Argument(help="Payment (listing price plus any late fee)")],
):
    """Return a rented game with payment."""
    with get_cli_session() as db:
        customer = _login(db, username, password)
        rental = db.get(Rental, rental_id)
        if not rental:
            print(f"Rental {rental_id} not found!")
            raise typer.Exit(1)
        try:
            payment = customer.return_game(rental, amount)
        except ValueError as e:
            print(e)
            raise typer.Exit(1)
        print(f"Returned. {payment}")


if __name__ == "__main__":
    cli()
