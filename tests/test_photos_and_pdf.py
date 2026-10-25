"""Pictures that show in the chat, and a conversation as a PDF made here.

The bias is A FILE THE PHONE CAN'T SHOW. A picture sent as a document
is a grey icon to tap and open in another app; a Markdown file on a
phone is a page of asterisks. So the tests check a picture goes as a
photo -- but ``/file NAME``, asking for the file itself, still gets the
original -- and one Telegram refuses as a photo still arrives, as a
document. And the PDF: made by a browser from the conversation's words
only (a tool's output never, a script never run), named as the Markdown
file is, kept in ``shared/``; with no browser the person still gets the
Markdown file and is told why, rather than nothing.
"""

from __future__ import annotations

import asyncio
import os
import stat

import httpx
import pytest

from dvara import past, printed
from tests.conftest import says
from tests.test_telegram import KNOWN, FakeTelegram, make_bot, message  # noqa: F401

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


def _folder(service, actor="mahen", agent="greeter"):
    work = service.state / "work" / actor / agent
    work.mkdir(parents=True, exist_ok=True)
    return work


# ---- pictures as photos (telegram.py) ---------------------------------------------


def test_a_picture_in_a_notice_is_sent_as_a_photo(make_bot, tmp_path):  # noqa: F811
    fake = FakeTelegram()
    bot = make_bot(fake)
    shot = tmp_path / "porch.png"
    shot.write_bytes(PNG)
    asyncio.run(bot._deliver_notice(str(KNOWN), "Someone at the door", file=shot))
    [photo] = fake.of("sendPhoto")
    assert 'filename="porch.png"' in photo["multipart"]
    assert "Someone at the door" in photo["multipart"]
    assert fake.of("sendDocument") == []


def test_a_file_that_isnt_a_picture_is_still_a_document(make_bot, tmp_path):  # noqa: F811
    fake = FakeTelegram()
    bot = make_bot(fake)
    report = tmp_path / "report.md"
    report.write_text("# week 40\n")
    asyncio.run(bot._deliver_notice(str(KNOWN), "This week's report", file=report))
    assert fake.of("sendPhoto") == []
    assert 'filename="report.md"' in fake.of("sendDocument")[0]["multipart"]


def test_a_picture_telegram_refuses_as_a_photo_goes_as_a_document(make_bot, tmp_path):  # noqa: F811
    fake = FakeTelegram()
    fake.status["sendPhoto"] = [httpx.Response(
        400, json={"ok": False, "description": "Bad Request: PHOTO_INVALID_DIMENSIONS"})]
    bot = make_bot(fake)
    tall = tmp_path / "receipt.jpg"
    tall.write_bytes(b"\xff\xd8\xff" + b"\0" * 32)
    asyncio.run(bot._deliver_notice(str(KNOWN), "Your receipt", file=tall))
    assert len(fake.of("sendPhoto")) == 1
    assert 'filename="receipt.jpg"' in fake.of("sendDocument")[0]["multipart"]


def test_a_picture_too_big_for_a_photo_is_not_tried_as_one(make_bot, tmp_path,  # noqa: F811
                                                           monkeypatch):
    from dvara import telegram
    monkeypatch.setattr(telegram, "PHOTO_LIMIT", 4)
    fake = FakeTelegram()
    bot = make_bot(fake)
    big = tmp_path / "scan.png"
    big.write_bytes(PNG)
    asyncio.run(bot._deliver_notice(str(KNOWN), "The scan", file=big))
    assert fake.of("sendPhoto") == []
    assert len(fake.of("sendDocument")) == 1


def test_asking_for_a_picture_by_name_sends_the_original(make_bot, make_service):  # noqa: F811
    from dvara.actors import ActorBook
    service = make_service([], actors=ActorBook.from_dict({"actor": {
        "mahen": {"channel": [{"kind": "telegram", "id": KNOWN}]}}}))
    (_folder(service) / "plan.png").write_bytes(PNG)
    fake = FakeTelegram([message("/file plan.png")])
    asyncio.run(make_bot(fake, service=service).run())
    assert fake.of("sendPhoto") == []
    assert 'filename="plan.png"' in fake.of("sendDocument")[0]["multipart"]


# ---- a conversation as a PDF (printed.py) -----------------------------------------


def say(service, text, *, actor="owner", thread="chat"):
    return asyncio.run(service.deliver(actor=actor, agent="greeter",
                                       thread=thread, text=text))


@pytest.fixture
def fake_browser(tmp_path, monkeypatch):
    """A 'browser' that copies the page it was given into the PDF it was
    asked for, so a test can read what would have been printed."""
    script = tmp_path / "fake-chrome"
    script.write_text('#!/bin/sh\nfor a; do case "$a" in --print-to-pdf=*) out="${a#*=}";; '
                      'file://*) src="${a#file://}";; esac; done\n'
                      'printf "%%PDF-1.4\\n" > "$out"; cat "$src" >> "$out"\n')
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("YANTRA_BROWSER_EXECUTABLE", str(script))
    return script


def test_export_pdf_is_printed_from_the_words_and_kept_in_shared(make_service,
                                                                  fake_browser):
    service = make_service([says("Bleed it with the key <b>slowly</b>.")])
    say(service, "how do I bleed a radiator? <script>x()</script>")
    sent = say(service, "/chats export 1 pdf")
    [made] = sent.files
    assert made.parent.name == "shared"
    assert made.name.endswith("-how-do-i-bleed-a-radiator-script-x-script.pdf")
    page = made.read_text()
    assert page.startswith("%PDF")
    assert "&lt;script&gt;x()&lt;/script&gt;" in page and "<script>" not in page
    assert "&lt;b&gt;slowly&lt;/b&gt;" in page
    assert "default-src 'none'" in page            # nothing for the page to fetch
    assert "as a PDF" in sent.text and sent.stop_reason == "files"


def test_with_no_browser_the_markdown_file_comes_and_says_why(make_service, monkeypatch):
    monkeypatch.setenv("YANTRA_BROWSER_EXECUTABLE", "")
    monkeypatch.setattr(printed, "BROWSERS", ())
    service = make_service([says("Friday.")])
    say(service, "when is the trip?")
    sent = say(service, "/chats export 1 pdf")
    [made] = sent.files
    assert made.suffix == ".md"
    assert "couldn't make a PDF" in sent.text


def test_the_pdf_word_is_read_and_others_are_not():
    assert past.export_pick("/chats export 2 pdf") == 2
    assert past.export_as("/chats export 2 pdf") == "pdf"
    assert past.export_as("/chats export 2 PDF") == "pdf"
    assert past.export_as("/chats export 2") == "md"
    assert past.export_pick("/chats export 2 docx") is None


def test_a_tools_output_never_reaches_the_page():
    kept = {"title": "t", "started_at": "", "entries": [
        {"who": "you", "text": "read my note"},
        {"who": "tool", "name": "read_file", "text": "wifi password hunter2"},
        {"who": "agent", "text": "Done."}]}
    page = printed.html_of(kept, agent="minder")
    assert "read_file" in page and "hunter2" not in page


def test_the_page_can_ask_for_the_pdf(make_service, fake_browser):
    from fastapi.testclient import TestClient

    from dvara.http import create_app
    from tests.test_past import finish

    service = make_service([says("Lisbon in May.")], web=True)
    token = "a-token-long-enough-to-be-real"
    auth = {"Authorization": f"Bearer {token}"}
    with TestClient(create_app(service, token=token)) as client:
        finish(client, auth, "where should we go?")
        [row] = client.get("/web/chats", headers=auth, params={"actor": "owner"}).json()["rows"]
        got = client.get(f"/web/chats/{row['id']}/export", headers=auth,
                         params={"actor": "owner", "as": "pdf"})
        assert got.status_code == 200 and got.headers["content-type"] == "application/pdf"
        assert "where-should-we-go.pdf" in got.headers["content-disposition"]
        assert b"Lisbon in May." in got.content


@pytest.mark.skipif(printed.browser() is None, reason="no browser on this machine")
def test_a_real_browser_prints_every_script(tmp_path):
    kept = {"title": "नमस्ते", "started_at": "2026-10-24T18:05:00+00:00", "entries": [
        {"who": "you", "text": "Say hello in Hindi 🙂"},
        {"who": "agent", "text": "नमस्ते — namaste."}]}
    made = asyncio.run(printed.pdf_to(tmp_path, kept, agent="minder", zone="Asia/Kolkata"))
    assert made.read_bytes().startswith(b"%PDF") and made.stat().st_size > 1000
    assert not any(p.name.startswith("dvara-print-") for p in tmp_path.iterdir())
    assert os.access(made, os.R_OK)
