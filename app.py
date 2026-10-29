import math
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime

from flask import Flask, render_template, request, redirect, url_for

GENRES = ["Contemporary", "Historical", "Fantasy", "Rom-Com", "Paranormal",
          "Romantic Suspense", "Young Adult", "Other"]
STATUSES = {"want": "Want to read", "reading": "Reading", "finished": "Finished"}
RING_RADIUS = 44
RING_LENGTH = 2 * math.pi * RING_RADIUS


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or os.environ.get("DB_PATH", "books.db")

    @contextmanager
    def db():
        conn = sqlite3.connect(app.config["DB_PATH"])
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db():
        with db() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS books ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "title TEXT NOT NULL, "
                "author TEXT NOT NULL DEFAULT 'Unknown author', "
                "genre TEXT NOT NULL DEFAULT 'Contemporary', "
                "status TEXT NOT NULL DEFAULT 'want', "
                "rating INTEGER NOT NULL DEFAULT 0, "
                "review TEXT NOT NULL DEFAULT '', "
                "pages INTEGER, "
                "added_on TEXT NOT NULL, "
                "finished_on TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS settings ("
                "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )

    init_db()

    @app.template_filter("pretty_date")
    def pretty_date(value):
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%d %b %Y")
        except (TypeError, ValueError):
            return ""

    def clean_book(form):
        title = form.get("title", "").strip()[:200]
        author = form.get("author", "").strip()[:120] or "Unknown author"
        genre = form.get("genre", "Contemporary")
        if genre not in GENRES:
            genre = "Contemporary"
        status = form.get("status", "want")
        if status not in STATUSES:
            status = "want"
        try:
            pages = int(form.get("pages", ""))
            pages = pages if 1 <= pages <= 5000 else None
        except ValueError:
            pages = None
        try:
            rating = max(0, min(5, int(form.get("rating", 0))))
        except ValueError:
            rating = 0
        review = form.get("review", "").strip()[:1000]
        return title, author, genre, status, pages, rating, review

    def get_goal(conn):
        row = conn.execute("SELECT value FROM settings WHERE key = 'goal'").fetchone()
        return int(row["value"]) if row else 12

    def apply_status(conn, book_id, status, today):
        if status == "finished":
            conn.execute(
                "UPDATE books SET status = 'finished', "
                "finished_on = COALESCE(finished_on, ?) WHERE id = ?",
                (today, book_id))
        else:
            conn.execute(
                "UPDATE books SET status = ?, finished_on = NULL WHERE id = ?",
                (status, book_id))

    @app.route("/")
    def index():
        status = request.args.get("status", "all")
        genre = request.args.get("genre", "")
        q = request.args.get("q", "").strip()
        sort = request.args.get("sort", "newest")
        today = date.today()
        year = str(today.year)

        sql = "SELECT * FROM books WHERE 1=1"
        params = []
        if status in STATUSES:
            sql += " AND status = ?"
            params.append(status)
        if genre in GENRES:
            sql += " AND genre = ?"
            params.append(genre)
        if q:
            sql += " AND (title LIKE ? OR author LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]
        order = {
            "title": " ORDER BY title COLLATE NOCASE",
            "author": " ORDER BY author COLLATE NOCASE, title COLLATE NOCASE",
            "rating": " ORDER BY rating DESC, id DESC",
        }.get(sort, " ORDER BY id DESC")
        sql += order

        with db() as conn:
            books = conn.execute(sql, params).fetchall()
            counts = {r["status"]: r["n"] for r in conn.execute(
                "SELECT status, COUNT(*) AS n FROM books GROUP BY status")}
            total = sum(counts.values())
            avg = conn.execute(
                "SELECT AVG(rating) FROM books WHERE rating > 0").fetchone()[0]
            finished_year = conn.execute(
                "SELECT COUNT(*) FROM books WHERE status = 'finished' "
                "AND finished_on LIKE ?", (year + "%",)).fetchone()[0]
            goal = get_goal(conn)
            genre_rows = conn.execute(
                "SELECT genre, COUNT(*) AS n FROM books "
                "GROUP BY genre ORDER BY n DESC, genre").fetchall()
            top_rated = conn.execute(
                "SELECT title, author, rating FROM books WHERE rating > 0 "
                "ORDER BY rating DESC, id DESC LIMIT 3").fetchall()

        pct = min(100, int(finished_year * 100 / goal)) if goal else 0
        biggest = genre_rows[0]["n"] if genre_rows else 1
        genre_bars = [
            {"genre": r["genre"], "n": r["n"], "pct": int(r["n"] * 100 / biggest)}
            for r in genre_rows
        ]
        return render_template(
            "index.html",
            books=books, total=total, counts=counts,
            avg=round(avg, 1) if avg else 0,
            finished_year=finished_year, goal=goal, pct=pct, year=year,
            ring_length=round(RING_LENGTH, 2),
            ring_offset=round(RING_LENGTH * (1 - pct / 100), 2),
            genre_bars=genre_bars, top_rated=top_rated,
            status=status, genre=genre, q=q, sort=sort,
            genres=GENRES, statuses=STATUSES,
        )

    @app.route("/add", methods=["POST"])
    def add():
        title, author, genre, status, pages, rating, review = clean_book(request.form)
        if title:
            today = date.today().isoformat()
            with db() as conn:
                conn.execute(
                    "INSERT INTO books (title, author, genre, status, rating, "
                    "review, pages, added_on, finished_on) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (title, author, genre, status, rating if status == "finished" else 0,
                     review, pages, today, today if status == "finished" else None))
        return redirect(url_for("index"))

    @app.route("/edit/<int:book_id>", methods=["POST"])
    def edit(book_id):
        title, author, genre, status, pages, rating, review = clean_book(request.form)
        if title:
            with db() as conn:
                conn.execute(
                    "UPDATE books SET title = ?, author = ?, genre = ?, pages = ?, "
                    "rating = ?, review = ? WHERE id = ?",
                    (title, author, genre, pages, rating, review, book_id))
                apply_status(conn, book_id, status, date.today().isoformat())
        return redirect(url_for("index"))

    @app.route("/status/<int:book_id>", methods=["POST"])
    def set_status(book_id):
        status = request.form.get("status", "want")
        if status in STATUSES:
            with db() as conn:
                apply_status(conn, book_id, status, date.today().isoformat())
                if status == "finished" and request.form.get("rating"):
                    _, _, _, _, _, rating, review = clean_book(request.form)
                    conn.execute(
                        "UPDATE books SET rating = ?, review = ? WHERE id = ?",
                        (rating, review, book_id))
        return redirect(url_for("index"))

    @app.route("/rate/<int:book_id>", methods=["POST"])
    def rate(book_id):
        try:
            rating = max(0, min(5, int(request.form.get("rating", 0))))
        except ValueError:
            rating = 0
        with db() as conn:
            current = conn.execute(
                "SELECT rating FROM books WHERE id = ?", (book_id,)).fetchone()
            if current is not None:
                new = 0 if current["rating"] == rating else rating
                conn.execute("UPDATE books SET rating = ? WHERE id = ?", (new, book_id))
        return redirect(url_for("index"))

    @app.route("/delete/<int:book_id>", methods=["POST"])
    def delete(book_id):
        with db() as conn:
            conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
        return redirect(url_for("index"))

    @app.route("/goal", methods=["POST"])
    def goal():
        try:
            value = int(request.form.get("goal", 12))
        except ValueError:
            value = 12
        value = max(1, min(365, value))
        with db() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('goal', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (str(value),))
        return redirect(url_for("index"))

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
