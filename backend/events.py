from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, auth
from audit import log_action
from typing import Optional
from constants import default_term_dates, TERM_ORDER

router = APIRouter(prefix="/api/events", tags=["Events"])

# Term-date configuration + auto current-term detection
cal_router = APIRouter(prefix="/api/calendar", tags=["Calendar"])

ALL_TERMS = ["Term 1", "Term 2", "Term 3"]


def _term_ranges(db: Session, year: int):
    """Return ({term: (start, end)}, is_default) for a year — configured rows if
    present, otherwise the standard Kenyan defaults."""
    rows = db.query(models.TermDate).filter(models.TermDate.academic_year == year).all()
    if rows:
        return {r.term: (r.start_date, r.end_date) for r in rows}, False
    return default_term_dates(year), True


def compute_current_term(db: Session, today: date | None = None):
    """Resolve (academic_year, term, source) for a date from configured/default ranges.
    In-range wins; during a holiday gap the next upcoming term is used; after the
    last term ends, the final term is kept."""
    today = today or date.today()
    year = today.year
    ranges, is_default = _term_ranges(db, year)
    source = "default" if is_default else "configured"

    for term in ALL_TERMS:
        rng = ranges.get(term)
        if rng and rng[0] <= today <= rng[1]:
            return year, term, source

    upcoming = sorted(
        ((t, ranges[t][0]) for t in ALL_TERMS if ranges.get(t) and today < ranges[t][0]),
        key=lambda x: x[1],
    )
    if upcoming:
        return year, upcoming[0][0], source
    return year, "Term 3", source


@cal_router.get("/current-term", response_model=schemas.CurrentTermResponse)
def get_current_term(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    year, term, source = compute_current_term(db)
    return {"academic_year": year, "term": term, "source": source}


@cal_router.get("/term-dates", response_model=schemas.TermDatesResponse)
def get_term_dates(
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    year = year or date.today().year
    ranges, is_default = _term_ranges(db, year)
    terms = [
        {"term": t, "start_date": ranges[t][0], "end_date": ranges[t][1]}
        for t in ALL_TERMS if t in ranges
    ]
    return {"academic_year": year, "is_default": is_default, "terms": terms}


@cal_router.put("/term-dates", response_model=schemas.TermDatesResponse)
def set_term_dates(
    payload: schemas.TermDatesPayload,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Only admins and the principal can set term dates")

    for item in payload.terms:
        if item.term not in ALL_TERMS:
            raise HTTPException(status_code=400, detail=f"Invalid term: {item.term}")
        if item.end_date < item.start_date:
            raise HTTPException(status_code=400, detail=f"{item.term}: end date is before start date")
        row = db.query(models.TermDate).filter(
            models.TermDate.academic_year == payload.academic_year,
            models.TermDate.term == item.term,
        ).first()
        if row:
            row.start_date = item.start_date
            row.end_date = item.end_date
            row.updated_by = current_user.name
        else:
            db.add(models.TermDate(
                academic_year=payload.academic_year,
                term=item.term,
                start_date=item.start_date,
                end_date=item.end_date,
                updated_by=current_user.name,
            ))
    log_action(db, current_user.id, "UPDATE", "term_dates", payload.academic_year,
               {"year": payload.academic_year})
    db.commit()

    ranges, is_default = _term_ranges(db, payload.academic_year)
    terms = [
        {"term": t, "start_date": ranges[t][0], "end_date": ranges[t][1]}
        for t in ALL_TERMS if t in ranges
    ]
    return {"academic_year": payload.academic_year, "is_default": is_default, "terms": terms}


@router.get("/")
def list_events(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    q = db.query(models.SchoolEvent)
    if year:
        from sqlalchemy import extract
        q = q.filter(extract("year", models.SchoolEvent.start_date) == year)
    if month:
        from sqlalchemy import extract
        q = q.filter(extract("month", models.SchoolEvent.start_date) == month)
    events = q.order_by(models.SchoolEvent.start_date).all()
    return [_serialize(e) for e in events]


@router.post("/", status_code=201)
def create_event(
    event: schemas.EventCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal", "secretary", "teacher"}:
        raise HTTPException(status_code=403, detail="Not authorized")

    new_event = models.SchoolEvent(
        title=event.title,
        description=event.description,
        event_type=event.event_type,
        start_date=event.start_date,
        end_date=event.end_date,
        all_day=event.all_day,
        created_by=current_user.name,
    )
    db.add(new_event)
    db.flush()
    log_action(db, current_user.id, "CREATE", "event", new_event.id, {"title": event.title})
    db.commit()
    db.refresh(new_event)
    return _serialize(new_event)


@router.put("/{event_id}")
def update_event(
    event_id: int,
    event: schemas.EventCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal", "secretary", "teacher"}:
        raise HTTPException(status_code=403, detail="Not authorized")

    row = db.query(models.SchoolEvent).filter(models.SchoolEvent.id == event_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")

    for field, value in event.model_dump().items():
        setattr(row, field, value)

    log_action(db, current_user.id, "UPDATE", "event", event_id, {"title": event.title})
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.delete("/{event_id}", status_code=204)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Not authorized")

    row = db.query(models.SchoolEvent).filter(models.SchoolEvent.id == event_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")

    log_action(db, current_user.id, "DELETE", "event", event_id)
    db.delete(row)
    db.commit()


def _serialize(e: models.SchoolEvent) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "description": e.description,
        "event_type": e.event_type,
        "start_date": e.start_date,
        "end_date": e.end_date,
        "all_day": e.all_day,
        "created_by": e.created_by,
        "created_at": e.created_at,
    }
