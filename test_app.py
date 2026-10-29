import pytest
from app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "test.db"))
    app.config["TESTING"] = True
    return app.test_client()


def page(client, url="/"):
    return client.get(url).get_data(as_text=True)


def add(client, title="Pride and Prejudice", **extra):
    data = {"title": title, "author": "Jane Austen", "genre": "Historical"}
    data.update(extra)
    return client.post("/add", data=data)


def test_health(client):
    assert client.get("/health").get_json() == {"status": "ok"}


def test_home_page_loads(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Heartbound" in r.data


def test_empty_shelf_message(client):
    assert "Your shelf is empty" in page(client)


def test_add_book(client):
    add(client)
    html = page(client)
    assert "Pride and Prejudice" in html and "Jane Austen" in html
    assert "g-historical" in html and "Want to read" in html


def test_blank_title_is_ignored(client):
    add(client, title="   ")
    assert "Your shelf is empty" in page(client)


def test_invalid_values_fall_back_to_defaults(client):
    client.post("/add", data={"title": "Odd", "genre": "Nope", "status": "zzz", "pages": "abc"})
    html = page(client)
    assert "g-contemporary" in html and "Want to read" in html and "abc" not in html


def test_missing_author_gets_default(client):
    client.post("/add", data={"title": "Mystery Author"})
    assert "Unknown author" in page(client)


def test_start_reading_then_finish(client):
    add(client)
    client.post("/status/1", data={"status": "reading"})
    assert "Pride and Prejudice" in page(client, "/?status=reading")
    client.post("/status/1", data={"status": "finished"})
    html = page(client, "/?status=finished")
    assert "Pride and Prejudice" in html and "Finished on" in html


def test_finish_counts_toward_goal(client):
    add(client)
    client.post("/goal", data={"goal": "4"})
    client.post("/status/1", data={"status": "finished"})
    html = page(client)
    assert "25%" in html and "1 of 4" in html


def test_goal_is_clamped(client):
    client.post("/goal", data={"goal": "99999"})
    assert 'value="365"' in page(client)
    client.post("/goal", data={"goal": "0"})
    assert 'value="1"' in page(client)


def test_rating_toggle(client):
    add(client, status="finished")
    client.post("/rate/1", data={"rating": "4"})
    assert page(client).count('class="h on"') == 4
    client.post("/rate/1", data={"rating": "4"})
    assert page(client).count('class="h on"') == 0


def test_hearts_hidden_until_finished(client):
    add(client)
    assert 'title="Click a heart to rate"' not in page(client)
    client.post("/status/1", data={"status": "finished"})
    assert 'title="Click a heart to rate"' in page(client)


def test_edit_book_and_review(client):
    add(client)
    client.post("/edit/1", data={"title": "Persuasion", "author": "Jane Austen", "genre": "Historical",
                                 "status": "finished", "rating": "5", "review": "Absolutely lovely.", "pages": "250"})
    html = page(client)
    assert "Persuasion" in html and "Absolutely lovely." in html and "250 pages" in html
    assert page(client).count('class="h on"') == 5


def test_leaving_finished_clears_finish_date(client):
    add(client, status="finished")
    assert "Finished on" in page(client)
    client.post("/status/1", data={"status": "reading"})
    assert "Finished on" not in page(client)


def test_filters_and_search(client):
    add(client, title="Emma")
    add(client, title="Outlander", genre="Fantasy", author="Diana")
    assert "Emma" not in page(client, "/?genre=Fantasy")
    assert "Outlander" in page(client, "/?genre=Fantasy")
    assert "Outlander" in page(client, "/?q=diana")
    assert "Emma" not in page(client, "/?q=diana")


def test_sort_by_rating(client):
    add(client, title="LowBook", status="finished", rating="2")
    add(client, title="HighBook", status="finished", rating="5")
    html = page(client, "/?sort=rating")
    assert html.index("HighBook") < html.index("LowBook")


def test_average_rating_and_top_rated(client):
    add(client, title="A", status="finished", rating="4")
    add(client, title="B", status="finished", rating="2")
    html = page(client)
    assert "3.0" in html and "Top rated" in html


def test_delete_book(client):
    add(client)
    client.post("/delete/1")
    assert "Pride and Prejudice" not in page(client)


def test_html_is_escaped(client):
    add(client, title="<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in page(client)
