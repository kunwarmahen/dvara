"""Bias: a rule file that grants more than the owner thinks it does.

Every test here is aimed at one of three ways that happens, and none of
them looks wrong in a diff.

A WILDCARD IN AN ALLOW. `command = "git status*"` reads as a narrowing
and matches `git status; rm -rf ~`; `path = "~/notes/*"` reads as one
directory and matches `~/notes/../../.ssh/id_rsa`. The format refuses
these at load time rather than trusting anybody to notice, so most of the
loader tests below are about the exact shapes of that refusal.

A RULE THAT LOOSENS THE RUNG. The ladder's whole property is "tighten,
never loosen", and a per-call allow is the obvious way to put a hole in
it. So the composition is tested at every rung, including the two where
an allow must do nothing at all.

AN APPENDED RULE THAT UNDOES AN EARLIER ONE. Order-independence is the
reason the strictest match wins rather than the first, and the test for
it writes the rules in both orders.

The fourth bias is smaller and only shows up in production: `fnmatch`
consults the platform and `fnmatchcase` does not. A policy file whose
meaning depends on which machine the service booted on is not a policy
file, so case sensitivity is pinned.
"""

from __future__ import annotations

import asyncio

import pytest
from yantra import (
    PermissionRequest,
    adecide,
    allow_read_only,
    denial_code,
    denial_text,
    yolo,
)

from dvara.asks import AskDesk
from dvara.errors import ConfigProblem
from dvara.gate import Policy
from dvara.rules import RuleBook


def book(text: str) -> RuleBook:
    import tomllib
    return RuleBook.from_dict(tomllib.loads(text), where="policy.toml")


def request(*, read_only: bool = False, tool: str = "bash",
            **arguments) -> PermissionRequest:
    return PermissionRequest(tool_name=tool, arguments=arguments,
                             summary=arguments.get("command", "..."),
                             read_only=read_only)


def gate(rules: RuleBook, *, mode: str = "ask", desk: AskDesk | None = None,
         package: str = "ask", actor_mode: str | None = None):
    return Policy(mode=mode, rules=rules).gate(
        package, actor_mode=actor_mode, desk=desk,
        actor="owner", agent="ops", thread="t1")


def settle(gate_fn, req):
    """One decision, whether it answered a bool or a coroutine."""
    return asyncio.run(adecide(gate_fn, req))


ALLOW_GIT = '''
[[rule]]
tool = "bash"
args = { command = "git status" }
verdict = "allow"
'''

DENY_ENV = '''
[[rule]]
tool = "write_file"
args = { path = "*.env" }
verdict = "deny"
reason = "secrets are not edited by an agent; ask me and I will do it"
'''


# ---- matching ---------------------------------------------------------------


class TestMatching:
    def test_a_rule_with_no_args_matches_every_call_to_that_tool(self):
        rules = book('[[rule]]\ntool = "bash"\nverdict = "deny"\n')
        assert rules.decide("bash", {"command": "anything"}).verdict == "deny"
        assert rules.decide("write_file", {}) is None

    def test_the_tool_may_be_a_pattern_when_it_is_not_an_allow(self):
        rules = book('[[rule]]\ntool = "browser_*"\nverdict = "deny"\n')
        assert rules.decide("browser_click", {}).verdict == "deny"
        assert rules.decide("read_file", {}) is None

    def test_every_named_argument_must_match(self):
        rules = book('''
[[rule]]
tool = "write_file"
args = { path = "*.py", content = "*TODO*" }
verdict = "deny"
''')
        assert rules.decide("write_file", {"path": "a.py",
                                           "content": "x TODO y"}) is not None
        assert rules.decide("write_file", {"path": "a.py",
                                           "content": "done"}) is None

    def test_a_list_is_alternatives_for_one_argument(self):
        rules = book('''
[[rule]]
tool = "bash"
args = { command = ["git status", "git diff"] }
verdict = "allow"
''')
        assert rules.decide("bash", {"command": "git diff"}).verdict == "allow"
        assert rules.decide("bash", {"command": "git push"}) is None

    def test_a_missing_argument_does_not_match(self):
        rules = book(DENY_ENV)
        assert rules.decide("write_file", {}) is None

    def test_a_non_string_argument_never_matches(self):
        """str() of a list is a Python repr that happens to be text, and
        matching against it would mean the file said one thing and the
        gate did another."""
        rules = book(DENY_ENV)
        assert rules.decide("write_file", {"path": ["a.env", "b.env"]}) is None

    def test_matching_is_case_sensitive_on_every_platform(self):
        """fnmatch consults the platform; fnmatchcase does not."""
        rules = book(DENY_ENV)
        assert rules.decide("write_file", {"path": "a.env"}) is not None
        assert rules.decide("write_file", {"path": "a.ENV"}) is None


class TestTheStrictestWins:
    ALLOW_THEN_DENY = '''
[[rule]]
tool = "bash"
args = { command = "git status" }
verdict = "allow"

[[rule]]
tool = "bash"
verdict = "deny"
'''
    DENY_THEN_ALLOW = '''
[[rule]]
tool = "bash"
verdict = "deny"

[[rule]]
tool = "bash"
args = { command = "git status" }
verdict = "allow"
'''

    def test_order_does_not_change_the_answer(self):
        """A rule appended at the bottom cannot quietly undo one at the
        top, which is the property that makes a diff of this file mean
        what it looks like it means."""
        for text in (self.ALLOW_THEN_DENY, self.DENY_THEN_ALLOW):
            assert book(text).decide(
                "bash", {"command": "git status"}).verdict == "deny"

    def test_ask_beats_allow_and_loses_to_deny(self):
        rules = book('''
[[rule]]
tool = "bash"
verdict = "ask"

[[rule]]
tool = "bash"
args = { command = "git status" }
verdict = "allow"
''')
        assert rules.decide("bash", {"command": "git status"}).verdict == "ask"

    def test_a_tie_keeps_the_first_reason_written(self):
        rules = book('''
[[rule]]
tool = "bash"
verdict = "deny"
reason = "first"

[[rule]]
tool = "bash"
verdict = "deny"
reason = "second"
''')
        assert rules.decide("bash", {}).reason == "first"


# ---- the loader -------------------------------------------------------------


class TestRefusingAWildcardInAnAllow:
    def test_the_shell_escape_is_refused_by_name(self):
        with pytest.raises(ConfigProblem, match="rm -rf"):
            book('''
[[rule]]
tool = "bash"
args = { command = "git status*" }
verdict = "allow"
''')

    def test_the_path_traversal_is_refused_by_the_same_rule(self):
        with pytest.raises(ConfigProblem, match="wildcard"):
            book('''
[[rule]]
tool = "write_file"
args = { path = "~/notes/*" }
verdict = "allow"
''')

    def test_a_pattern_in_an_allow_rules_TOOL_is_refused_too(self):
        with pytest.raises(ConfigProblem, match="wildcard"):
            book('[[rule]]\ntool = "browser_*"\nverdict = "allow"\n')

    def test_every_wildcard_character_counts(self):
        for pattern in ("git statu?", "git status[12]", "git *"):
            with pytest.raises(ConfigProblem, match="wildcard"):
                book(f'''
[[rule]]
tool = "bash"
args = {{ command = "{pattern}" }}
verdict = "allow"
''')

    def test_one_bad_alternative_spoils_the_list(self):
        with pytest.raises(ConfigProblem, match="wildcard"):
            book('''
[[rule]]
tool = "bash"
args = { command = ["git status", "git *"] }
verdict = "allow"
''')

    def test_patterns_are_fine_in_a_deny_and_in_an_ask(self):
        for verdict in ("deny", "ask"):
            rules = book(f'''
[[rule]]
tool = "bash"
args = {{ command = "rm -rf*" }}
verdict = "{verdict}"
''')
            assert rules.decide("bash", {"command": "rm -rf /"}) is not None


class TestTheFileItself:
    def test_an_unknown_key_is_an_error(self):
        with pytest.raises(ConfigProblem, match="unknown key"):
            book('[[rule]]\ntool = "bash"\nverdict = "deny"\nwhen = "always"\n')

    def test_a_misspelled_verdict_is_an_error(self):
        """A rule with no verdict is a standing denial that does nothing."""
        with pytest.raises(ConfigProblem, match="deny, ask, allow"):
            book('[[rule]]\ntool = "bash"\nverdict = "denied"\n')

    def test_an_unknown_table_is_an_error(self):
        with pytest.raises(ConfigProblem, match="unknown table"):
            book('[actor.mahen]\nagents = ["ops"]\n')

    def test_a_single_rule_table_is_accepted(self):
        assert len(book('[rule]\ntool = "bash"\nverdict = "deny"\n')) == 1

    def test_args_must_be_a_table(self):
        with pytest.raises(ConfigProblem, match="args must be a table"):
            book('[[rule]]\ntool = "bash"\nargs = ["git status"]\n'
                 'verdict = "deny"\n')

    def test_an_empty_alternative_list_is_an_error(self):
        with pytest.raises(ConfigProblem, match="non-empty list"):
            book('[[rule]]\ntool = "bash"\nargs = { command = [] }\n'
                 'verdict = "deny"\n')

    def test_a_reason_on_an_allow_is_an_error(self):
        """An approval is silent, so the sentence would never be read."""
        with pytest.raises(ConfigProblem, match="never says anything"):
            book('[[rule]]\ntool = "bash"\nverdict = "allow"\n'
                 'reason = "because I said so"\n')

    def test_a_missing_file_is_no_policy_unless_it_was_named(self, tmp_path):
        missing = tmp_path / "policy.toml"
        assert len(RuleBook.from_toml(missing)) == 0
        with pytest.raises(ConfigProblem, match="no policy file"):
            RuleBook.from_toml(missing, required=True)

    def test_a_broken_file_is_always_loud(self, tmp_path):
        path = tmp_path / "policy.toml"
        path.write_text("[[rule]\n")
        with pytest.raises(ConfigProblem):
            RuleBook.from_toml(path)


# ---- the composition --------------------------------------------------------


class TestNoRulesIsNoChange:
    def test_an_empty_book_returns_yantras_own_functions(self):
        """Not "behaves the same" -- IS the same object. The property that
        keeps every service built before rules existed working."""
        assert gate(RuleBook(), mode="ask", package="ask") is allow_read_only
        assert gate(RuleBook(), mode="yolo", package="yolo") is yolo


class TestARuleMayTighten:
    def test_a_deny_bites_under_yolo(self):
        denied = request(command="rm -rf /")
        assert settle(gate(book('[[rule]]\ntool = "bash"\nverdict = "deny"\n'),
                           mode="yolo", package="yolo"), denied) is False
        assert denial_code(denied) == "policy"

    def test_a_deny_bites_a_read_only_tool(self):
        """"Never read my ssh keys" is a thing an owner may mean, and the
        read-only shortcut must not talk over it."""
        rules = book('''
[[rule]]
tool = "read_file"
args = { path = "*/.ssh/*" }
verdict = "deny"
''')
        req = request(tool="read_file", read_only=True,
                      path="/home/o/.ssh/id_rsa")
        assert settle(gate(rules, mode="yolo", package="yolo"), req) is False

    def test_an_ask_turns_a_yolo_call_into_a_question(self):
        rules = book('[[rule]]\ntool = "bash"\nverdict = "ask"\n')
        desk = AskDesk(timeout=5)
        fn = gate(rules, mode="yolo", package="yolo", desk=desk)

        async def go():
            req = request(command="rm -rf /")
            deciding = asyncio.create_task(adecide(fn, req))
            while not desk.pending():
                await asyncio.sleep(0)
            desk.answer(desk.pending()[0].id, actor="owner", approve=False)
            assert await deciding is False
            assert denial_code(req) == "user"

        asyncio.run(go())

    def test_an_ask_rule_reaches_a_read_only_tool_too(self):
        """"Tell me before this thing reads anything" is allowed to mean
        what it says, so this path has no read-only shortcut."""
        rules = book('[[rule]]\ntool = "read_file"\nverdict = "ask"\n')
        desk = AskDesk(timeout=5)
        fn = gate(rules, mode="ask", package="ask", desk=desk)

        async def go():
            req = request(tool="read_file", read_only=True, path="a.txt")
            deciding = asyncio.create_task(adecide(fn, req))
            while not desk.pending():
                await asyncio.sleep(0)
            desk.answer(desk.pending()[0].id, actor="owner", approve=True)
            assert await deciding is True

        asyncio.run(go())

    def test_an_ask_with_nowhere_to_go_is_a_denial(self):
        """Note 02's sentence, one level down: a question with no route
        was never a question."""
        rules = book('[[rule]]\ntool = "bash"\nverdict = "ask"\n')
        req = request(command="ls")
        assert settle(gate(rules, mode="yolo", package="yolo", desk=None),
                      req) is False


class TestARuleMayNotLoosen:
    def test_an_allow_answers_a_question_the_rung_would_have_asked(self):
        desk = AskDesk(timeout=5)
        fn = gate(book(ALLOW_GIT), mode="ask", package="ask", desk=desk)
        assert settle(fn, request(command="git status")) is True
        assert desk.pending() == [], "nobody should have been woken up"

    def test_an_allow_grants_nothing_under_read_only(self):
        """The rung that means 'do not wake this person' has no question
        for a standing answer to answer."""
        desk = AskDesk(timeout=5)
        fn = gate(book(ALLOW_GIT), mode="read_only", package="ask", desk=desk)
        req = request(command="git status")
        assert settle(fn, req) is False
        assert denial_code(req) == "unattended"

    def test_an_allow_grants_nothing_to_a_tightened_actor(self):
        desk = AskDesk(timeout=5)
        fn = gate(book(ALLOW_GIT), mode="ask", package="ask", desk=desk,
                  actor_mode="read_only")
        req = request(command="git status")
        assert settle(fn, req) is False
        # And the refusal does not blame an absence: note 02 recorded this
        # sentence as wrong for a tightened actor, and here both facts are
        # in hand. Somebody WAS available -- just not to this conversation.
        assert "not permitted to put questions" in denial_text(req)
        assert "nobody is available" not in denial_text(req)

    def test_an_allow_grants_nothing_with_no_desk(self):
        """No route means no question, and a standing answer to a question
        nobody can ask is not a permission."""
        fn = gate(book(ALLOW_GIT), mode="ask", package="ask", desk=None)
        assert settle(fn, request(command="git status")) is False

    def test_the_same_file_reads_differently_for_the_owner_and_a_guest(self):
        desk = AskDesk(timeout=5)
        rules = book(ALLOW_GIT)
        owner = gate(rules, mode="ask", package="ask", desk=desk)
        guest = gate(rules, mode="ask", package="ask", desk=desk,
                     actor_mode="read_only")
        assert settle(owner, request(command="git status")) is True
        assert settle(guest, request(command="git status")) is False

    def test_a_near_miss_is_asked_and_not_refused(self):
        """The cost of exact-match allows: a question, which is where the
        call started anyway."""
        desk = AskDesk(timeout=5)
        fn = gate(book(ALLOW_GIT), mode="ask", package="ask", desk=desk)

        async def go():
            req = request(command="git status --short")
            deciding = asyncio.create_task(adecide(fn, req))
            while not desk.pending():
                await asyncio.sleep(0)
            desk.answer(desk.pending()[0].id, actor="owner", approve=True)
            assert await deciding is True

        asyncio.run(go())


class TestWhatTheModelIsTold:
    def test_a_standing_denial_says_not_to_wait_and_retry(self):
        """The failure this sentence prevents: a model treating a policy
        refusal like a timeout and trying again in a minute."""
        req = request(tool="write_file", path="/srv/.env", content="x")
        assert settle(gate(book(DENY_ENV), mode="yolo", package="yolo"),
                      req) is False
        told = denial_text(req)
        assert "standing rule" in told
        assert "retrying will not change it" in told

    def test_the_owners_own_reason_reaches_the_model(self):
        req = request(tool="write_file", path="/srv/.env", content="x")
        settle(gate(book(DENY_ENV), mode="yolo", package="yolo"), req)
        assert "ask me and I will do it" in denial_text(req)

    def test_a_policy_refusal_is_distinguishable_from_a_human_one(self):
        req = request(tool="write_file", path="/srv/.env", content="x")
        settle(gate(book(DENY_ENV), mode="yolo", package="yolo"), req)
        assert denial_code(req) == "policy"

    def test_an_approval_leaves_no_reason_behind(self):
        desk = AskDesk(timeout=5)
        allowed = request(command="git status")
        settle(gate(book(ALLOW_GIT), mode="ask", package="ask", desk=desk),
               allowed)
        assert allowed.reason is None
        assert allowed.code is None
