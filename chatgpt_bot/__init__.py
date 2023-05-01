"""A small library that helps you to create ChatGPT bots."""
import sqlite3
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import openai


class Conversation:
    """The main class for the library."""

    def __init__(
        self,
        conversation_id: str,
        api_key: str,
        system_prompt: str = "You are a helpful virtual assistant.",
        database_filename: str = "database.sqlite3",
        model: str = "gpt-3.5-turbo",
        message_limit: Optional[int] = None,
    ):
        """
        Initialize the class.

        conversation_id - A random conversation ID (whatever you want).
        api_key - Your OpenAI API key.
        system_prompt - The ChatGPT system prompt you want to use.
        database_filename - Where you want to save the database."
        model - The ChatGPT model version to use.
        message_limit - The number of messages to retrieve from history every time.
        """
        openai.api_key = api_key
        self._conversation_id = conversation_id
        self._system_prompt = system_prompt
        self._message_limit = message_limit
        self._model = model
        self._con = sqlite3.connect(database_filename)
        self._cur = self._con.cursor()

        self._cur.execute(
            """
        CREATE TABLE IF NOT EXISTS "Message" (
          "id" INTEGER PRIMARY KEY AUTOINCREMENT,
          "timestamp" DATETIME NOT NULL,
          "conversation_id" TEXT NOT NULL,
          "role" TEXT NOT NULL,
          "message" TEXT NOT NULL
        )
        """
        )

        self._cur.execute(
            """
        CREATE INDEX IF NOT EXISTS "idx_message__conversation_id" ON "Message" ("conversation_id");
        """
        )
        self._con.commit()

    def _add_message(self, message: str, user: bool) -> None:
        """Add a message to the database."""
        self._cur.execute(
            """
        INSERT INTO "Message"
        (timestamp, conversation_id, role, message)
        VALUES
        (datetime(strftime('%s', 'now'), 'unixepoch'), ?, ?, ?);""",
            (self._conversation_id, "user" if user else "assistant", message),
        )

        self._con.commit()

    def _get_messages(self) -> List[Dict[str, Any]]:
        """Retrieve all messages from the database."""
        if self._message_limit:
            self._cur.execute(
                """
            SELECT id, timestamp, role, message FROM "Message" WHERE
            conversation_id=?
            ORDER BY timestamp DESC
            LIMIT ?;
            """,
                (self._conversation_id, self._message_limit),
            )
        else:
            self._cur.execute(
                """
            SELECT id, timestamp, role, message FROM "Message" WHERE
            conversation_id=?
            ORDER BY timestamp DESC
            """,
                (self._conversation_id,),
            )

        messages = [
            {"id": x[0], "timestamp": x[1], "role": x[2], "message": x[3]}
            for x in reversed(self._cur.fetchall())
        ]
        return messages

    def ask(self, message: str) -> str:
        """Ask ChatGPT a question."""
        chat = [{"role": "system", "content": self._system_prompt}]
        self._add_message(message, user=True)
        chat.extend(
            [{"role": m["role"], "content": m["message"]} for m in self._get_messages()]
        )
        completion = openai.ChatCompletion.create(
            model=self._model, messages=chat, temperature=0.3
        )
        reply = completion["choices"][0]["message"]["content"].strip()
        self._add_message(reply, user=False)
        return reply
