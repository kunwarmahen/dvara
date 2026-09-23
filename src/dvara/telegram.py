"""A Telegram bot, as a CLIENT of this service rather than a part of it.

Every note before this one was written so that this module could be
small. It holds no roster, no mapping from a chat to a person, no
permission logic and no idea what a budget is; it moves text between
Telegram's HTTP API and ``Service.deliver``, and it puts a question where
a person can press a button on it. Everything it knows about who is
talking it learns by ASKING the roster, which is note 05's whole point
arriving at the place that needed it.

Three things were left to decide, and they are the three the medium
forces on you.

**A REPLY HAS A BOTTOM AT 4096, AND IT IS MEASURED IN UTF-16.** This is
the one that bites in production rather than in a test. Telegram counts
a message in UTF-16 code units, and Python counts a string in code
points -- so an answer of 3000 characters can be 4200 units and be
rejected whole, and the ones that do it are emoji, CJK beyond the basic
plane, and the mathematical letters a model reaches for in a formula.
``utf16_len`` is the measure everything here uses.

A reply over the cap is SPLIT, never truncated. A brief that stops mid
sentence still looks like an answer, and the citations that would tell
you it is not are at the bottom, which is precisely the part truncation
removes. Splitting cuts at the widest boundary that does not waste half
a message -- a blank line, then a newline, then a space -- and the cut
is always at a Python character boundary, so a surrogate pair cannot be
split in half by the very arithmetic that counts it.

**THE POLL LOOP NEVER AWAITS A TURN.** A turn that asks to run a tool
suspends until a person approves it; the approval arrives as a button
press; button presses arrive through the long poll. Await the turn in
the loop and the answer can only arrive down the pipe the turn is
holding shut -- every escalated call would wait out its deadline and be
refused for a silence that had somebody sitting there pressing the
button. So an update becomes a task, and the loop goes straight back to
polling. Two messages in one chat are serialized by the service's own
per-session lock rather than by this loop, which is why it is safe to
let go of them here.

**AN OFFSET IS AN ACKNOWLEDGEMENT, AND IT IS SPENT WHEN THE MESSAGE IS
TAKEN.** Telegram redelivers an update until you ask for one past it, so
where the offset moves decides what a crash does. Moving it after the
turn buys at-least-once: the process dies mid-answer and the same
message runs again on the next boot, spending an allowance twice and
possibly running a tool twice. AN AGENT TURN IS NOT IDEMPOTENT, so this
takes the other one. The offset moves when the update is taken, a crash
loses the message, and the person who watched their message go
unanswered is the one participant in the whole system who can simply
send it again.

The same argument is why a backlog is dropped by default. A bot that was
down for a day comes up holding a day of messages, and answering "what
changed today?" nine hours late is a wrong answer delivered
confidently -- while a queue of ten spends ten turns of somebody's
allowance in one breath. ``--catch-up`` is there for the owner who
knows their backlog is worth running; the startup line says how many
were passed over, because a message that silently evaporates is
indistinguishable from a bot that is broken.

## Rate limits

Telegram publishes one message per second per chat and roughly thirty
overall, and enforces it with a 429 carrying ``retry_after``. Both halves
are handled, and they are different problems:

* **A minimum gap between two sends into one chat**, kept here so a long
  answer split into four parts does not become four hundred milliseconds
  of flooding. A turn-shaped bot sends one message per turn and never
  notices this; the split reply is exactly the case that does.
* **``retry_after`` is obeyed as an instruction**, but only up to a
  ceiling. A flood wait of five minutes is longer than the deadline on
  the question it would have delivered, and A WAIT LONGER THAN THE
  DEADLINE IS NOT A WAIT, IT IS A FAILURE -- better to raise, which for
  a notifier is a delivery that failed, which the desk already knows how
  to read.

## Plain text, on purpose

Nothing here sets ``parse_mode``. Markdown and HTML modes make the
MODEL'S PUNCTUATION A SYNTAX ERROR: an answer with one unmatched
asterisk, or a stray ``_`` in a filename, comes back as a 400 and the
person gets nothing at all. Splitting formatted text is worse again --
a cut through a code fence renders the second half as prose. So a reply
goes out as what it is, and the one piece of decoration this service ever
wanted (note 06 guessed at italics for the receipt) is a plain line under
a blank one.

## What a bot is allowed to decide

Almost nothing, and the boundary is worth naming because it is where a
channel adapter usually goes wrong.

* **One bot is one agent.** A token IS an identity -- a name, a picture,
  an @handle somebody types -- and hanging a roster off one of them means
  a person prefixing every message forever. A second agent is a second
  token from BotFather and a second process, and dvara invents no command
  dialect.
* **An unknown identity gets SILENCE, not a sentence.** The roster's
  refusal is polite and says nothing about who else exists, but saying it
  to every stranger who finds the bot makes a service out of the
  refusal. The line goes to the owner's own stderr instead, because the
  owner is the only person who can act on it, and ``--as telegram:ID``
  exists so a mapping can be proved before any of this is running.
* **A question is one message and is not split.** The reply is prose and
  survives being cut; a decision does not. An oversized summary is
  elided in the MIDDLE, keeping the verb at the front and the target at
  the end, which are the two parts a person is actually deciding about.
* **An approval is never a message.** Typing "yes" into the chat queues
  that message behind the very turn it was meant to release
  (``service.py``), so the question carries buttons and the press lands
  on ``AskDesk.answer`` down a path the turn is not holding.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys

import httpx

from dvara.actors import Channel
from dvara.asks import Ask, NotYours
from dvara.errors import ConfigProblem, Refused
from dvara.locks import KeyedLocks
from dvara.service import Service

#: Telegram's own base. Settable so a test can point at a transport and
#: an owner behind a proxy can point somewhere else.
API_BASE = "https://api.telegram.org"

#: One message, in UTF-16 code units. Telegram's number, not a guess.
MESSAGE_LIMIT = 4096

#: One inline button's ``callback_data``, in BYTES. An ask id is 22
#: characters of urlsafe base64 and the verdict prefix is two more, so
#: 24 of these 64 are spent -- stated here because the day somebody
#: lengthens an id is the day this silently stops round-tripping.
CALLBACK_LIMIT = 64

#: How long ``getUpdates`` is allowed to hold the connection open. Long
#: polling, so the usual state of this process is one idle socket rather
#: than a request every second.
POLL_SECONDS = 25

#: The floor on the gap between two sends into the SAME chat. Telegram
#: publishes one per second and tolerates bursts; the margin is for the
#: split reply, which is the only thing here that ever sends four.
SEND_GAP = 1.05

#: A typing indicator lasts five seconds at Telegram's end, so it has to
#: be renewed. The only feedback a turn-shaped medium has while a model
#: is thinking -- and cheaper than the alternative the service refused,
#: which is a bot that edits one message forty times.
TYPING_EVERY = 4.0

#: The longest ``retry_after`` worth honouring. Past this the wait
#: outlives the question it was going to deliver.
MAX_RETRY_AFTER = 60.0

#: Where a long poll goes after a network error, doubling, in seconds.
#: A bot on a laptop lid meets this every day and should come back on its
#: own rather than needing a restart.
BACKOFF_START, BACKOFF_MAX = 1.0, 30.0


class TelegramError(RuntimeError):
    """Telegram said no to one call, in a way that is not the owner's fault.

    Distinguished from ``ConfigProblem`` by who can fix it. A bad token
    or a second poller is a person's mistake and stops the process; a 400
    on one message is this call's problem and nothing else's.
    """


def utf16_len(text: str) -> int:
    """The length Telegram will measure, not the one Python reports.

    Every character outside the Basic Multilingual Plane -- emoji, and
    the mathematical alphabets a model reaches for in a formula -- is one
    Python character and TWO of these. An answer of 3000 characters can
    therefore be 4200 units and be refused whole, which is the bug this
    function exists to make impossible to write.
    """
    return len(text.encode("utf-16-le")) // 2


def _fits(text: str, limit: int) -> int:
    """The largest character count whose UTF-16 length is within ``limit``.

    Binary searched rather than counted, and bounded above by ``limit``
    itself: every character is at least one unit, so a prefix longer than
    the limit cannot possibly fit.
    """
    if utf16_len(text) <= limit:
        return len(text)
    low, high = 0, min(len(text), limit)
    while low < high:
        mid = (low + high + 1) // 2
        if utf16_len(text[:mid]) <= limit:
            low = mid
        else:
            high = mid - 1
    return low


def split_message(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    """One reply, as the messages Telegram will accept, in order.

    SPLIT, NEVER TRUNCATE. A brief cut off at 4096 characters still reads
    as a finished answer, and the citations that would give it away are
    at the bottom -- which is the part a truncation removes. Whoever asked
    gets all of it or knows they did not.

    The cut walks outward from the hard limit looking for a blank line, a
    newline, then a space, and TAKES ONE ONLY IF IT DOES NOT WASTE HALF A
    MESSAGE. Without that floor a single space near the front of a 4000
    character run of prose would produce a three-word message followed by
    the same problem, which is a splitter that makes no progress.

    Every cut is at a Python character boundary, so the arithmetic that
    counts UTF-16 units can never split a surrogate pair in half.
    """
    text = text.strip()
    if not text:
        return []
    parts: list[str] = []
    while utf16_len(text) > limit:
        hard = _fits(text, limit)
        head = text[:hard]
        cut = hard
        for boundary in ("\n\n", "\n", " "):
            found = head.rfind(boundary)
            if found > hard // 2:
                cut = found
                break
        chunk, text = text[:cut].rstrip(), text[cut:].lstrip()
        if chunk:
            parts.append(chunk)
        if not text:
            return parts
    parts.append(text)
    return parts


def elide(text: str, limit: int) -> str:
    """Keep both ends of one string and say that the middle went.

    For a question, never for an answer. A person approving ``bash`` is
    deciding about a verb at the front and a target at the end, and a cut
    that keeps only the front hands them the half that never changes.
    """
    if utf16_len(text) <= limit:
        return text
    marker = "\n[... elided ...]\n"
    budget = max(limit - utf16_len(marker), 0)
    head = _fits(text, budget // 2)
    # The tail is measured from the end by walking backwards over what is
    # left of the budget, one character at a time, because there is no
    # "largest SUFFIX that fits" to binary search -- reversing the string
    # would put a surrogate pair back to front and count it wrong.
    spare, tail = budget - utf16_len(text[:head]), len(text)
    while tail > head and spare - utf16_len(text[tail - 1]) >= 0:
        tail -= 1
        spare -= utf16_len(text[tail])
    return text[:head].rstrip() + marker + text[tail:].lstrip()


class _Pacer:
    """The floor on how often this process sends into one chat.

    One lock per chat, so the four parts of a split reply go out in
    order, and an earliest-next-send stamp so they go out a second apart.
    The lock is the half that matters: two tasks interleaving their
    chunks would deliver one person two half-answers shuffled together.

    Neither table grows with the number of chats the bot has ever seen.
    A lock goes when nobody holds or waits on it (``locks.py``), and a
    stamp goes once it is in the past -- a stamp that has already passed
    makes ``wait`` return at once, which is what no stamp does too.
    """

    def __init__(self, gap: float = SEND_GAP) -> None:
        self.gap = gap
        self._locks: KeyedLocks[int] = KeyedLocks()
        self._next: dict[int, float] = {}

    def lock(self, chat: int):
        return self._locks.hold(chat)

    async def wait(self, chat: int) -> None:
        loop = asyncio.get_running_loop()
        due = self._next.get(chat, 0.0) - loop.time()
        if due > 0:
            await asyncio.sleep(due)

    def sent(self, chat: int) -> None:
        now = asyncio.get_running_loop().time()
        for stale in [c for c, due in self._next.items() if due <= now]:
            del self._next[stale]
        self._next[chat] = now + self.gap


class TelegramBot:
    """One bot token, one agent, however many people the roster allows.

    Constructed around a ``Service`` rather than around an HTTP client:
    this runs IN the service's process and reaches ``AskDesk`` directly,
    which is what lets a question be pushed the moment it is raised
    instead of waiting out a poll of ``GET /asks``. The HTTP surface
    stays what it always was -- the way an adapter that is NOT in this
    process gets in.
    """

    def __init__(self, service: Service, *, token: str, agent: str,
                 catch_up: bool = False,
                 poll_seconds: int = POLL_SECONDS,
                 send_gap: float = SEND_GAP,
                 client: httpx.AsyncClient | None = None,
                 log=None) -> None:
        if not token or ":" not in token:
            raise ConfigProblem(
                "$TELEGRAM_TOKEN must be the token BotFather gave you, which "
                "looks like 8675309:AA... -- and it belongs in the "
                "environment, never on a command line where the shell "
                "history and every `ps` on the box can read it")
        self.service = service
        self.agent = agent
        self.catch_up = catch_up
        self.poll_seconds = poll_seconds
        #: Where the owner's own lines go. None means "whatever stderr is
        #: at the moment of writing" rather than whatever it was when this
        #: module was imported -- the difference matters to anything that
        #: redirects it after the fact, a test harness being the obvious
        #: one and a supervisor rotating a log being the other.
        self.log = log
        # Validated here rather than on the first message. An owner who
        # typed the agent's name wrong finds out at startup, where they
        # are looking, instead of finding out from a stranger's silence.
        self.spec = service.roster.spec(agent)
        self._url = f"{API_BASE}/bot{token}"
        self._client = client or httpx.AsyncClient(timeout=poll_seconds + 15)
        self._owns_client = client is None
        self._pacer = _Pacer(send_gap)
        self._turns: set[asyncio.Task] = set()
        self._stopping = asyncio.Event()

    # ---- the loop ----------------------------------------------------------

    async def run(self) -> None:
        """Poll, hand each update to a task, and never block on one.

        The ``route`` registration is what makes this a channel rather
        than a second front door: a question put to a person who has a
        ``telegram`` entry in the actors file is delivered here, and it
        does not matter one bit whether the turn that raised it arrived
        over Telegram, over HTTP or from the owner's own terminal.
        """
        if self.service.asks is not None:
            self.service.asks.route("telegram", self._deliver_ask)
        me = await self._api("getMe")
        offset = await self._first_offset()
        self._note(f"dvara · telegram · @{me.get('username', '?')} "
                   f"→ {self.agent}")
        backoff = BACKOFF_START
        try:
            while not self._stopping.is_set():
                # ONE YIELD PER ROUND, so the loop cannot starve the turns
                # it started. A long poll normally suspends on the socket
                # for twenty-five seconds and every task in the process
                # gets its turn for free -- but an endpoint that answers
                # instantly (a proxy, `--poll-seconds 0`, an error being
                # returned as fast as it can be asked for) turns this into
                # a tight loop of awaits that never actually suspend, and
                # the answer somebody is waiting for never advances a
                # step. One line, against a failure that looks like a bot
                # gone quiet at full CPU.
                await asyncio.sleep(0)
                try:
                    updates = await self._api(
                        "getUpdates", offset=offset,
                        timeout=self.poll_seconds,
                        allowed_updates=["message", "callback_query"])
                    backoff = BACKOFF_START
                except (httpx.HTTPError, TelegramError) as exc:
                    # A lid closed, a DNS blip, a 500 at their end. None
                    # of those is a reason to need a restart, and the
                    # backoff is what stops a dead network becoming a
                    # spin.
                    self._note(f"telegram: {type(exc).__name__}: {exc} "
                               f"(retrying in {backoff:g}s)")
                    await self._sleep(backoff)
                    backoff = min(backoff * 2, BACKOFF_MAX)
                    continue
                for update in updates:
                    # SPENT WHEN TAKEN. See the module docstring: the
                    # alternative redelivers a turn that already charged
                    # somebody for it.
                    offset = update["update_id"] + 1
                    self._spawn(self._handle(update))
        finally:
            await self._shutdown()

    def _note(self, line: str) -> None:
        """One line for the owner, never for a chat."""
        print(line, file=self.log or sys.stderr)

    def stop(self) -> None:
        """Leave the loop after the poll in flight comes back."""
        self._stopping.set()

    async def _first_offset(self) -> int:
        """Where to start reading, and what to do about what is already there.

        ``offset=-1`` asks Telegram for the last update only, which is how
        you learn the high-water mark without consuming the queue. Past
        it is where a fresh bot starts.
        """
        if self.catch_up:
            return 0
        latest = await self._api("getUpdates", offset=-1, limit=1, timeout=0)
        if not latest:
            return 0
        offset = latest[0]["update_id"] + 1
        # Deliberately loud, and deliberately vague about the count:
        # Telegram tells us the last id, not how many are behind it. A
        # message that vanished with no line anywhere looks exactly like
        # a bot that is broken.
        self._note("telegram: skipping the messages that arrived while this "
                   "was down (--catch-up answers them instead)")
        return offset

    def _spawn(self, coro) -> None:
        """Run it alongside the poll, and keep a reference so it survives.

        A bare ``ensure_future`` with nothing holding the result is a task
        the garbage collector may take mid-turn; the set is what keeps it
        alive, and the callback is what keeps the set from being a leak.
        """
        task = asyncio.ensure_future(coro)
        self._turns.add(task)
        task.add_done_callback(self._turns.discard)

    async def _shutdown(self) -> None:
        """Stop owing anybody anything: turns, then the socket.

        Cancelling a turn is safe rather than merely tolerable. Yantra
        leaves history resumable at a cancellation -- outstanding tool
        calls get synthesized results -- and ``Service.deliver`` records
        the Run as ``cancelled`` on the way past, so a bot stopped mid
        answer leaves a conversation that can be picked up and a row that
        says what happened.
        """
        for task in list(self._turns):
            task.cancel()
        if self._turns:
            await asyncio.gather(*self._turns, return_exceptions=True)
        if self._owns_client:
            await self._client.aclose()

    async def _sleep(self, seconds: float) -> None:
        """Sleep, unless somebody asks us to stop first."""
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._stopping.wait(), timeout=seconds)

    # ---- one update --------------------------------------------------------

    async def _handle(self, update: dict) -> None:
        """Whatever arrived, dealt with, and never raising into the loop.

        An exception here would take down the poll -- one malformed
        update and the bot is off the air until somebody notices. So the
        loop's contract is that this returns, and what went wrong goes to
        the owner's log.
        """
        try:
            if "callback_query" in update:
                await self._pressed(update["callback_query"])
            elif "message" in update:
                await self._message(update["message"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 -- see the docstring
            self._note(f"telegram: update {update.get('update_id')} failed: "
                       f"{type(exc).__name__}: {exc}")

    async def _message(self, message: dict) -> None:
        chat = int(message.get("chat", {}).get("id", 0))
        native = message.get("from", {}).get("id")
        if not chat or native is None:
            return
        try:
            self.service.actors.resolve("telegram", native)
        except Refused:
            # SILENCE, NOT A SENTENCE. To the owner, who can fix it; not
            # to the stranger, who would learn that something is here.
            self._note(f"telegram: {native} messaged and is not in the "
                       f"actors file (add [[actor.NAME.channel]] "
                       f"kind=\"telegram\" id={native})")
            return

        text = message.get("text")
        if text is None:
            # A photo, a sticker, a voice note. One sentence rather than
            # silence, because this person IS on the list and a bot that
            # ignores them is a bot they think is broken.
            await self._send(chat, "I can only read text.")
            return
        if text.strip().split()[:1] == ["/start"]:
            await self._send(chat, self._introduction())
            return

        # The first action is awaited rather than left to the task: a
        # person who sent a message wants the "typing" the moment they
        # sent it, and a task that has only been SCHEDULED shows nothing
        # until the loop next gets round to it.
        with contextlib.suppress(Exception):
            await self._api("sendChatAction", chat_id=chat, action="typing")
        typing = asyncio.ensure_future(self._typing(chat))
        try:
            reply = await self.service.deliver(
                via=Channel(kind="telegram", id=str(native)),
                agent=self.agent, thread=str(chat), text=text)
        finally:
            typing.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await typing
        if reply.detail and not reply.ok:
            # The channel gets the polite sentence; the owner, who is the
            # one person who can fix a bad base URL, gets the reason.
            self._note(f"telegram: {reply.stop_reason}: {reply.detail}")
        for chunk in self._reply_messages(reply.text, reply.receipt):
            await self._send(chat, chunk)

    def _introduction(self) -> str:
        """The one command Telegram itself defines, answered here.

        ``/start`` is not this service growing a command language -- it is
        the literal text of the button a person presses to open a chat
        with a bot, and forwarding it to a model produces an answer to a
        question nobody asked. What somebody pressing Start wants is what
        this is, which the package already says about itself.
        """
        lines = [self.spec.name or self.agent]
        if self.spec.description:
            lines.append(self.spec.description)
        lines.append("Send me a message and I will answer it.")
        return "\n\n".join(lines)

    def _reply_messages(self, text: str, receipt: str | None) -> list[str]:
        """The answer, and the line under it, as messages.

        THE RECEIPT RIDES ON THE LAST PART. On the first of three it is a
        footer in the middle of an answer; in a message of its own it is
        a second notification buzz and another second of pacing, for one
        short line. Only when it genuinely will not fit does it become
        its own.
        """
        parts = split_message(text or "")
        if not receipt:
            return parts
        if not parts:
            return [receipt]
        tail = f"{parts[-1]}\n\n{receipt}"
        if utf16_len(tail) <= MESSAGE_LIMIT:
            parts[-1] = tail
        else:
            parts.append(receipt)
        return parts

    async def _typing(self, chat: int) -> None:
        """"…is typing", RENEWED until the turn ends -- the first one is
        sent by the caller, so this starts by waiting.

        Failures are swallowed on purpose: a chat action that cannot be
        sent is a cosmetic loss, and letting it cancel somebody's answer
        would be the tail wagging the dog. It bypasses the pacer because
        an action is not a message and does not count against the limit
        the pacer exists to respect.
        """
        while True:
            await asyncio.sleep(TYPING_EVERY)
            with contextlib.suppress(Exception):
                await self._api("sendChatAction", chat_id=chat,
                                action="typing")

    # ---- the question, and the button --------------------------------------

    async def _deliver_ask(self, ask: Ask) -> None:
        """Put one "may I?" in front of the person it was addressed to.

        Sent to ``ask.to`` -- their own chat with this bot -- rather than
        to the thread the turn is running in. THE QUESTION IS THE
        PERSON'S. A turn in a group, or a turn that arrived over HTTP
        entirely, still asks them where they can answer it privately, and
        note 05 already put that address on the Ask so this module needs
        no table of its own to find it.

        Raising here is meaningful and is left to propagate: the desk
        reads a delivery that failed as a channel that is not listening,
        and refuses the call rather than spending the deadline on it.
        """
        data = [f"y:{ask.id}", f"n:{ask.id}"]
        if any(len(d.encode("utf-8")) > CALLBACK_LIMIT for d in data):
            raise TelegramError(
                f"an ask id of {len(ask.id)} characters does not fit in a "
                f"callback button; a question nobody can press is worse "
                f"than one that was never delivered")
        if ask.to is None:
            raise TelegramError(
                "this question carries no Telegram address; it was handed "
                "here by a catch-all notifier rather than by a route")
        head = f"{ask.agent} wants to run {ask.tool}:\n\n"
        body = elide(ask.summary, MESSAGE_LIMIT - utf16_len(head))
        await self._send(
            int(ask.to), head + body,
            reply_markup={"inline_keyboard": [[
                {"text": "approve", "callback_data": data[0]},
                {"text": "refuse", "callback_data": data[1]},
            ]]})

    async def _pressed(self, query: dict) -> None:
        """A button, turned into an answer at the desk.

        Who PRESSED decides who answered, resolved through the roster like
        any other inbound identity -- not who the message was addressed
        to, and not whose chat it is sitting in. ``AskDesk.answer``
        insists on both the id and the actor, so a question forwarded to
        somebody else is a press that resolves nothing.

        ``via="telegram"`` is the literal kind this adapter is, hardcoded
        because this is the one module in the repo that IS Telegram. The
        service still never branches on the string; it writes it onto the
        Run so that "where were you when you approved this?" has an
        answer.
        """
        query_id = query.get("id", "")
        native = query.get("from", {}).get("id")
        verdict, _, ask_id = str(query.get("data", "")).partition(":")
        if self.service.asks is None or not ask_id \
                or verdict not in ("y", "n"):
            await self._toast(query_id, "that button means nothing here")
            return
        try:
            actor = self.service.actors.resolve("telegram", native).id
        except Refused as exc:
            await self._toast(query_id, str(exc))
            return
        approve = verdict == "y"
        try:
            landed = self.service.asks.answer(ask_id, actor=actor,
                                              approve=approve, via="telegram")
        except NotYours as exc:
            # The id was forwarded, or an adapter is routing badly. Said
            # to the presser rather than swallowed: a button that does
            # nothing and explains nothing is the worst of the three.
            await self._toast(query_id, str(exc))
            return
        if not landed:
            await self._toast(query_id, "that question is no longer waiting")
            return
        await self._toast(query_id, "approved" if approve else "refused")
        await self._settle(query.get("message") or {}, approve)

    async def _settle(self, message: dict, approve: bool) -> None:
        """Replace the buttons with what was decided.

        Two jobs in one edit. A pair of buttons that stays pressable after
        the question is gone invites a second press that can do nothing,
        and the chat is the only place this decision is written down where
        the person who made it will ever look again.
        """
        chat = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        if chat is None or message_id is None:
            return
        decided = "approved" if approve else "refused"
        body = message.get("text", "")
        with contextlib.suppress(TelegramError, httpx.HTTPError):
            await self._api("editMessageText", chat_id=chat,
                            message_id=message_id,
                            text=f"{body}\n\n— {decided}")

    async def _toast(self, query_id: str, text: str) -> None:
        """Stop the spinner on the button, and say why if there is a why.

        Telegram leaves a pressed button spinning until this is called,
        so a press that is silently ignored looks like a bot that hung.
        """
        if not query_id:
            return
        with contextlib.suppress(TelegramError, httpx.HTTPError):
            await self._api("answerCallbackQuery", callback_query_id=query_id,
                            text=text[:200])

    # ---- the wire ----------------------------------------------------------

    async def _send(self, chat: int, text: str, **extra):
        """One message into one chat, no faster than the limit allows.

        No ``parse_mode``. See the module docstring: a mode makes the
        model's own punctuation a syntax error, and the failure is the
        whole answer rather than one italic word.
        """
        async with self._pacer.lock(chat):
            await self._pacer.wait(chat)
            try:
                return await self._api("sendMessage", chat_id=chat,
                                       text=text, **extra)
            finally:
                self._pacer.sent(chat)

    async def _api(self, method: str, **payload):
        """One Bot API call, with the two failures that are not ours.

        ``retry_after`` is obeyed as an instruction and only up to
        ``MAX_RETRY_AFTER``: a flood wait longer than the deadline on the
        question this was delivering is not a wait to sit through, it is
        a failure to report while somebody can still do something about
        it.

        A 401 or a 409 stops the process rather than being retried. Both
        are the owner's to fix and neither improves with time -- and a 409
        in particular is TWO POLLERS ON ONE TOKEN, which does not fail, it
        SPLITS: half of somebody's messages answered by a process nobody
        remembers starting.
        """
        url = f"{self._url}/{method}"
        for attempt in (1, 2):
            response = await self._client.post(
                url, json={k: v for k, v in payload.items() if v is not None})
            if response.status_code == 429 and attempt == 1:
                wait = _retry_after(response)
                if wait <= MAX_RETRY_AFTER:
                    await asyncio.sleep(wait)
                    continue
                raise TelegramError(
                    f"{method}: rate limited for {wait:g}s, which is longer "
                    f"than anything here is willing to wait")
            if response.status_code in (401, 403) and method == "getMe":
                raise ConfigProblem(
                    "Telegram refused this bot token; check $TELEGRAM_TOKEN "
                    "against what BotFather gave you")
            if response.status_code == 409:
                raise ConfigProblem(
                    "another process is already polling with this bot token; "
                    "two pollers do not collide, they split -- half the "
                    "messages go to whichever one asked last")
            body = _body(response)
            if response.status_code != 200 or not body.get("ok", False):
                raise TelegramError(
                    f"{method}: {response.status_code} "
                    f"{body.get('description') or response.text[:200]}")
            return body.get("result")
        raise TelegramError(f"{method}: gave up after a rate limit")


def _body(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _retry_after(response: httpx.Response) -> float:
    """How long Telegram asked for, or a second if it did not say."""
    parameters = _body(response).get("parameters")
    if isinstance(parameters, dict):
        wait = parameters.get("retry_after")
        if isinstance(wait, int | float) and not isinstance(wait, bool):
            return float(wait)
    return 1.0
