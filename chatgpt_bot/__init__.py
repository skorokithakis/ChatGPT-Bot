"""A small library that helps you to create ChatGPT bots."""
import json
import sqlite3
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from openai import OpenAI


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
        time_limit: Optional[int] = None,
    ):
        """
        Initialize the class.

        conversation_id - A random conversation ID (whatever you want).
        api_key - Your OpenAI API key.
        system_prompt - The ChatGPT system prompt you want to use.
        database_filename - Where you want to save the database."
        model - The ChatGPT model version to use.
        message_limit - The number of messages to retrieve from history every time.
        time_limit - Only send GPT previous messages exchanged within `time_limit` hours.
        """
        self._openai = OpenAI(api_key=api_key)
        self._conversation_id = conversation_id
        self._system_prompt = system_prompt
        self._message_limit = message_limit
        self._time_limit = time_limit
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
        CREATE TABLE IF NOT EXISTS "Metadata" (
          "id" INTEGER PRIMARY KEY AUTOINCREMENT,
          "conversation_id" TEXT NOT NULL UNIQUE,
          "metadata" BLOB NOT NULL
        )
        """
        )

        self._cur.execute(
            """
        CREATE INDEX IF NOT EXISTS "idx_message__conversation_id" ON "Message" ("conversation_id");
        """
        )
        self._cur.execute(
            """
        CREATE INDEX IF NOT EXISTS "idx_metadata__conversation_id" ON "Metadata" ("conversation_id");
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
        query = [
            """
            SELECT id, timestamp, role, message FROM "Message" WHERE
            conversation_id=?
            """
        ]

        if self._time_limit:
            query.append(
                f"AND timestamp >= datetime('now', '-{self._time_limit} hours')"
            )

        query.append("ORDER BY timestamp DESC")

        if self._message_limit:
            query.append(f"LIMIT {self._message_limit}")

        self._cur.execute(" ".join(query), (self._conversation_id,))
        messages = [
            {"id": x[0], "timestamp": x[1], "role": x[2], "message": x[3]}
            for x in reversed(self._cur.fetchall())
        ]
        return messages

    def get_metadata(self) -> Any:
        """Retrieve the metadata for the current conversation."""
        self._cur.execute(
            """SELECT id, metadata FROM "Metadata" WHERE conversation_id=?""",
            (self._conversation_id,),
        )
        metadata = self._cur.fetchone()
        if not metadata:
            return None
        return json.loads(metadata[1])

    def set_metadata(self, metadata):
        """Store some metadata for the current conversation."""
        self._cur.execute(
            """
            INSERT INTO Metadata (conversation_id, metadata)
            VALUES (?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                metadata = excluded.metadata;
            """,
            (self._conversation_id, json.dumps(metadata)),
        )
        self._con.commit()

    def ask(self, message: str, functions=None) -> dict[str, Any]:
        """Ask ChatGPT a question."""
        chat = [{"role": "system", "content": self._system_prompt}]
        self._add_message(message, user=True)
        chat.extend(
            [{"role": m["role"], "content": m["message"]} for m in self._get_messages()]
        )

        if functions:
            completion = self._openai.chat.completions.create(
                model=self._model, messages=chat, tools=functions
            )
        else:
            completion = self._openai.chat.completions.create(
                model=self._model, messages=chat
            )

        finish_reason = completion.choices[0].finish_reason
        if finish_reason == "tool_calls":
            response_message = completion.choices[0].message
            function_calls = []
            for tool_call in response_message.tool_calls:
                if tool_call.type != "function":
                    continue
                function_calls.append(
                    (tool_call.function.name, json.loads(tool_call.function.arguments))
                )
            self._add_message("Ok, done.", user=False)
            return {"type": "function", "data": function_calls}
        else:
            reply = completion.choices[0].message.content.strip()
            self._add_message(reply, user=False)
            return {"type": "text", "data": reply}
