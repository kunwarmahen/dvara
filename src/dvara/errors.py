"""Refusals -- the errors a service turns into sentences instead of tracebacks.

A harness at a keyboard may raise: the operator reads the traceback and
fixes the file. A service has nobody to read it. Every condition a
*person* could have caused -- an actor nobody has heard of, an agent they
may not reach, an allowance already spent -- becomes a ``Refused``, and
``Service.deliver`` turns it into a reply that says what happened and
what would fix it.

The boundary is deliberate and it is a security one too. ``Refused`` is
raised only where the answer is safe to say out loud. A package that
fails to load says "the agent is unavailable"; it does not quote a
traceback from somebody else's Python at a stranger in a chat window.
"""

from __future__ import annotations


class DvaraError(Exception):
    """Base for everything this package raises."""


class Refused(DvaraError):
    """The request was understood and will not be served.

    ``message`` is written FOR THE PERSON WHO ASKED, so it is allowed to
    reach a channel verbatim.
    """


class ConfigProblem(DvaraError):
    """The owner's own files are wrong.

    Separate from ``Refused`` because it is not a person's mistake and
    must never be answered into a channel: it is a startup failure, loud,
    for the one human who can fix it.
    """
