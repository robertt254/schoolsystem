from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, auth
from audit import log_action
from typing import Optional

router = APIRouter(prefix="/api/library", tags=["Library"])

FINE_PER_DAY = 10   # KES 10 per overdue day


def _book_response(book: models.LibraryBook) -> dict:
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "isbn": book.isbn,
        "category": book.category,
        "quantity": book.quantity,
        "available": book.available,
        "condition": book.condition,
        "acquired_date": book.acquired_date,
        "created_at": book.created_at,
    }


def _borrow_response(b: models.LibraryBorrow, book_title: str) -> dict:
    today = date.today()
    is_overdue = b.return_date is None and b.due_date < today
    return {
        "id": b.id,
        "book_id": b.book_id,
        "book_title": book_title,
        "borrower_type": b.borrower_type,
        "borrower_id": b.borrower_id,
        "borrower_name": b.borrower_name,
        "borrowed_date": b.borrowed_date,
        "due_date": b.due_date,
        "return_date": b.return_date,
        "fine_amount": float(b.fine_amount),
        "recorded_by": b.recorded_by,
        "is_overdue": is_overdue,
    }


# ── Books ──────────────────────────────────────────────────────────────────────

@router.get("/books")
def list_books(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    q = db.query(models.LibraryBook)
    if search:
        like = f"%{search}%"
        q = q.filter(
            models.LibraryBook.title.ilike(like) |
            models.LibraryBook.author.ilike(like) |
            models.LibraryBook.isbn.ilike(like)
        )
    if category:
        q = q.filter(models.LibraryBook.category == category)
    return [_book_response(b) for b in q.order_by(models.LibraryBook.title).all()]


@router.post("/books", status_code=201)
def add_book(
    book: schemas.BookCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal", "secretary"}:
        raise HTTPException(status_code=403, detail="Not authorized")

    if book.isbn:
        exists = db.query(models.LibraryBook).filter(models.LibraryBook.isbn == book.isbn).first()
        if exists:
            raise HTTPException(status_code=409, detail="A book with this ISBN already exists")

    new_book = models.LibraryBook(
        title=book.title,
        author=book.author,
        isbn=book.isbn,
        category=book.category,
        quantity=book.quantity,
        available=book.quantity,
        condition=book.condition,
        acquired_date=book.acquired_date,
    )
    db.add(new_book)
    db.flush()
    log_action(db, current_user.id, "CREATE", "library_book", new_book.id, {"title": book.title})
    db.commit()
    db.refresh(new_book)
    return _book_response(new_book)


@router.put("/books/{book_id}")
def update_book(
    book_id: int,
    update: schemas.BookUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal", "secretary"}:
        raise HTTPException(status_code=403, detail="Not authorized")

    book = db.query(models.LibraryBook).filter(models.LibraryBook.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    for field, value in update.model_dump(exclude_none=True).items():
        setattr(book, field, value)

    log_action(db, current_user.id, "UPDATE", "library_book", book_id)
    db.commit()
    db.refresh(book)
    return _book_response(book)


@router.delete("/books/{book_id}", status_code=204)
def delete_book(
    book_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Not authorized")

    book = db.query(models.LibraryBook).filter(models.LibraryBook.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if book.available < book.quantity:
        raise HTTPException(status_code=400, detail="Cannot delete: some copies are currently borrowed")

    log_action(db, current_user.id, "DELETE", "library_book", book_id, {"title": book.title})
    db.delete(book)
    db.commit()


# ── Borrows ────────────────────────────────────────────────────────────────────

@router.get("/borrows")
def list_borrows(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    q = db.query(models.LibraryBorrow)
    if active_only:
        q = q.filter(models.LibraryBorrow.return_date == None)
    borrows = q.order_by(models.LibraryBorrow.borrowed_date.desc()).all()
    book_ids = {b.book_id for b in borrows}
    books = {b.id: b.title for b in db.query(models.LibraryBook).filter(models.LibraryBook.id.in_(book_ids)).all()}
    return [_borrow_response(b, books.get(b.book_id, "Unknown")) for b in borrows]


@router.post("/borrows", status_code=201)
def create_borrow(
    borrow: schemas.BorrowCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    book = db.query(models.LibraryBook).filter(models.LibraryBook.id == borrow.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if book.available <= 0:
        raise HTTPException(status_code=400, detail="No copies currently available")

    new_borrow = models.LibraryBorrow(
        book_id=borrow.book_id,
        borrower_type=borrow.borrower_type,
        borrower_id=borrow.borrower_id,
        borrower_name=borrow.borrower_name,
        borrowed_date=date.today(),
        due_date=borrow.due_date,
        fine_amount=0,
        recorded_by=current_user.name,
    )
    book.available -= 1
    db.add(new_borrow)
    db.flush()
    log_action(db, current_user.id, "CREATE", "library_borrow", new_borrow.id,
               {"book": book.title, "borrower": borrow.borrower_name})
    db.commit()
    db.refresh(new_borrow)
    return _borrow_response(new_borrow, book.title)


@router.put("/borrows/{borrow_id}/return")
def return_book(
    borrow_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    borrow = db.query(models.LibraryBorrow).filter(models.LibraryBorrow.id == borrow_id).first()
    if not borrow:
        raise HTTPException(status_code=404, detail="Borrow record not found")
    if borrow.return_date:
        raise HTTPException(status_code=400, detail="Book already returned")

    today = date.today()
    borrow.return_date = today

    if today > borrow.due_date:
        days_late = (today - borrow.due_date).days
        borrow.fine_amount = days_late * FINE_PER_DAY

    book = db.query(models.LibraryBook).filter(models.LibraryBook.id == borrow.book_id).first()
    if book:
        book.available = min(book.available + 1, book.quantity)

    log_action(db, current_user.id, "UPDATE", "library_borrow", borrow_id,
               {"returned": str(today), "fine": float(borrow.fine_amount)})
    db.commit()
    db.refresh(borrow)
    return _borrow_response(borrow, book.title if book else "Unknown")
