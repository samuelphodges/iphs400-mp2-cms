"""Admin: record and manage Alumni Network Listings."""
from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import listings
from app.web import current_user, flash, get_db, render, verify_csrf

router = APIRouter(prefix="/admin/listings", dependencies=[Depends(current_user)])
csrf_required = [Depends(verify_csrf)]


def _listing_or_404(conn: sqlite3.Connection, listing_id: int) -> sqlite3.Row:
    listing = listings.get(conn, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="No such listing.")
    return listing


def _editor(request: Request, user, form: dict, listing: sqlite3.Row | None = None,
            status_code: int = 200, error: str | None = None):
    if error:
        flash(request, error, "error")
    return render(request, "admin/listing_edit.html",
                  {"title": "Edit listing" if listing else "New listing",
                   "form": form, "listing": listing}, status_code=status_code, user=user)


def _clean(name: str, email: str, class_year: str, consented: str,
           consent_date: str) -> tuple[dict, dict, str | None]:
    """Normalise the submitted fields; return (form, fields to save, error)."""
    name, email, class_year, consent_date = (v.strip() for v in
                                             (name, email, class_year, consent_date))
    form = {"name": name, "email": email, "class_year": class_year,
            "consented": bool(consented), "consent_date": consent_date}
    save: dict = {"name": name, "email": email, "class_year": None, "consent_date": None}
    if not name:
        return form, save, "A listing needs a name."
    if "@" not in email:
        return form, save, "A listing needs an email address."
    if class_year:
        if not (class_year.isdigit() and 1800 <= int(class_year) <= 2100):
            return form, save, "The class year must be a four-digit year, or blank."
        save["class_year"] = int(class_year)
    if consented:
        try:
            date.fromisoformat(consent_date)
        except ValueError:
            return form, save, "A consented listing needs a consent date (YYYY-MM-DD)."
        save["consent_date"] = consent_date
    return form, save, None


@router.get("")
def list_all(request: Request, user=Depends(current_user),
             conn: sqlite3.Connection = Depends(get_db)):
    return render(request, "admin/listing_list.html",
                  {"title": "Listings", "items": listings.list_listings(conn)}, user=user)


@router.get("/new")
def new_listing(request: Request, user=Depends(current_user)):
    return _editor(request, user, {"name": "", "email": "", "class_year": "",
                                   "consented": False,
                                   "consent_date": date.today().isoformat()})


@router.post("", dependencies=csrf_required)
def create_listing(request: Request, name: str = Form(""), email: str = Form(""),
                   class_year: str = Form(""), consented: str = Form(""),
                   consent_date: str = Form(""), user=Depends(current_user),
                   conn: sqlite3.Connection = Depends(get_db)):
    form, save, error = _clean(name, email, class_year, consented, consent_date)
    if error:
        return _editor(request, user, form, status_code=422, error=error)
    listing_id = listings.create(conn, recorded_by=user["id"], **save)
    flash(request, f"Listing “{form['name']}” saved.")
    return RedirectResponse(f"/admin/listings/{listing_id}/edit", status_code=303)


@router.get("/{listing_id}/edit")
def edit_listing(listing_id: int, request: Request, user=Depends(current_user),
                 conn: sqlite3.Connection = Depends(get_db)):
    listing = _listing_or_404(conn, listing_id)
    form = {**dict(listing), "class_year": listing["class_year"] or "",
            "consented": listing["consent_date"] is not None,
            "consent_date": listing["consent_date"] or date.today().isoformat()}
    return _editor(request, user, form, listing)


@router.post("/{listing_id}", dependencies=csrf_required)
def save_listing(listing_id: int, request: Request, name: str = Form(""),
                 email: str = Form(""), class_year: str = Form(""),
                 consented: str = Form(""), consent_date: str = Form(""),
                 user=Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    listing = _listing_or_404(conn, listing_id)
    form, save, error = _clean(name, email, class_year, consented, consent_date)
    if error:
        return _editor(request, user, form, listing, status_code=422, error=error)
    listings.update(conn, listing_id, **save)
    flash(request, f"Listing “{form['name']}” saved.")
    return RedirectResponse(f"/admin/listings/{listing_id}/edit", status_code=303)


@router.post("/{listing_id}/delete", dependencies=csrf_required)
def delete_listing(listing_id: int, request: Request,
                   conn: sqlite3.Connection = Depends(get_db)):
    listing = _listing_or_404(conn, listing_id)
    listings.delete(conn, listing_id)
    flash(request, f"Listing “{listing['name']}” deleted.")
    return RedirectResponse("/admin/listings", status_code=303)
