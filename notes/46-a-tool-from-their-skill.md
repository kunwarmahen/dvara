# 46 — A tool from their skill

*A skill an agent learned for somebody ([note 42](42-seeing-the-work.md))
is a recipe: the model loads it, reads it, and writes the command that
runs its script. Once it has worked again and again, Yantra can offer
the same script as one call with named fields (its notes/98), the shape
small local models get right most often. Yantra's page has a button for
it. Behind this service there was no way at all.*

## The owner's, on the settings page

A tool is code the agent can run in one call, and making one runs its
script once as a test. That is a decision about the machine, so it is
the owner's, on Sarathi's settings page, never a word in the chat (and
so never something a prompt hidden in somebody's mail can ask for).

`dvara settings show` lists, under each agent, every person's learned
skills for it (`promoting.learned`): who kept it, how often it worked and
failed, how many in a row, whether it has a script, whether it is a tool
already, and whether it has earned the suggestion (five in a row). The
page offers **Make it a tool** where there is one script and no tool yet.

PRESSING IT IS THE YES. The page says first that the script runs once as
a test and takes up to a few minutes; then `dvara settings tool AGENT
--person P --skill S` builds that person's agent (their folder, the
package's skills and theirs only), and Yantra's `propose_tool` writes
the definition and runs the test unasked. It is kept (`save_tool`) only
if the test passed, in that person's folder, so one person's tool never
appears in anyone else's agent. Sarathi gives the call this house's own
model.

## Found by the live run

The first try said the test answered *"no such tool: 'greet_someone'"*.
Every package here has an allow list, and a promoted tool's name is on
none of them, so Yantra's registry turned it away, the test probe
included. Yantra now admits a promoted tool wherever `load_skill` is
admitted (its notes/98, *A package with an allow list*); a deny still
wins.

## Receipt

A scratch package `helper` (`allow = ["bash", "read_file",
"load_skill"]`, skills on) and raj's learned `greet-someone` (worked 5,
failed 0, one script), `qwen3.8:latest`:

```
$ dvara settings show        → learned: raj · greet-someone · worked 5 · in a row 5
                               · script · suggest
$ dvara … --provider ollama --model qwen3.8:latest settings tool helper \
      --person raj --skill greet-someone
greet_someone ['{name}']  test {'name': 'Alice'} → "Hello, Alice!"  kept: True
$ dvara … say --actor raj --agent helper "Please greet Bob."
Hello, Bob!                  (one call: greet_someone)
```

On this machine's real Dvara, minder's card listed the owner's kept
`flight-status-check` (written steps, no script), with no button.

## What the tests hold

`tests/test_promoting.py`: the page sees each person's learned skills
and how they did; a passing test keeps the tool in that person's folder;
a failing one keeps nothing; a skill that isn't theirs, or a name that
is a path, makes nothing. Sarathi's `tests/test_settings_page.py`: the
call goes to Dvara with this house's model and needs whose and which.

## What is not here yet

* ~~**Undoing it from the page.**~~ **Stop using as a tool** beside it
  (`settings tool AGENT --person P --skill S --remove`, `unmake_tool`):
  `tool.json` and the `tool:` line go, the skill stays a recipe with its
  counters. Live: after it, "Please greet Carol." went back to
  `load_skill → bash` and still said *"Hello, Carol!"*.
* **A tool a person asks for from the chat.** Deliberately not: see
  above.
