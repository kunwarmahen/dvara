# 82 — A topic is a conversation

Telegram lets a bot's private chat have topics: a sidebar of threads,
each with its own name, like a group's forum. With topics mode on for
the bot (set in BotFather, among the bot's settings; Bot API 9.3),
every message a person writes arrives with the topic it was written in
(`message_thread_id`, `is_topic_message`).

Before this, Dvara read only the chat. Every topic was one conversation,
so *"plan the trip"* in one and *"fix the sink"* in another shared a
history, and every answer landed in the chat's own General thread, not
under the question.

## What it does

**EACH TOPIC IS ITS OWN CONVERSATION.** A message written in a topic runs
under its own thread, `telegram:<chat>/<topic>`, so it has its own
session, its own lock and its own place in `/chats`. Two topics answer
at once, as two conversations on the home page do
([notes/79](79-each-conversation-its-own-chat.md)). A message outside any
topic is the chat it always was, `telegram:<chat>`, and a bot without
topics mode is unchanged.

**EVERYTHING SENT WHILE ANSWERING GOES BACK INTO IT.** The answer, the
*typing…*, the *Working…* message with its steps, a file, a voice note
and the buttons under a held turn all go to the topic the question came
from. The chat id carries its topic (`telegram.Chat`, an int with a
`topic`), and the one place every Bot API call is made (`_api`) adds
`message_thread_id` wherever that chat is the `chat_id`. Calls about one
message by its id (an edit, a delete, a button's answer) take no topic,
so they're left alone. A held turn's buttons keep the topic too: the
hold's thread names it, so its rest of the answer goes back there.

**THE CHAT ITSELF WHEN A TOPIC IS REFUSED.** If Telegram answers *"message
thread not found"*, the topic was deleted, or the Bot API won't send
into a private chat's topic (reported against Bot API 10.0). The same
call is then made once more without the topic, and the owner's log says
which topic was refused. An answer outside its topic beats no answer.

## What it doesn't do

* **Make topics.** A topic is started by the person, in their Telegram
  app. `/new` in a topic starts that topic's conversation over; it
  doesn't open a new topic.
* **Name a topic after its conversation.** The topic keeps the name the
  person gave it.
* **Tell a reply thread from a topic by its id alone.** Only a message
  marked `is_topic_message` is in a topic. A reply in a group's thread
  can carry a `message_thread_id` too, and that stays the chat's own
  conversation (a reply carries an old conversation on as before:
  [notes/78](78-carried-on-where-it-was-written.md)).
* **Questions and notices in the topic.** A yes asked while a turn runs,
  and a schedule's notice, go to the person's chat, where they always
  went: they belong to the person, not to one conversation.

## Receipt

Tests only, against a stand-in Bot API. The house bot doesn't have
topics mode on, so this hasn't run against a real one.
`tests/test_telegram_topics.py`: a chat and its topic told apart, and a
reply thread not taken for a topic; the answer and the *typing* go back
into the topic it was asked in; two topics are two conversations, and
one's history isn't the other's; a chat without topics sends no
`message_thread_id`; a topic Telegram refuses is answered in the chat
itself, with a line in the owner's log.

Continues [notes/78](78-carried-on-where-it-was-written.md) (carried on
where it was written) and [notes/79](79-each-conversation-its-own-chat.md)
(each conversation its own chat).
