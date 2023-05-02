ChatGPT Bot
===========

This is a small library that tries to make it easier to create a ChatGPT bot. It has
a simple interface that keeps conversational context in a SQLite database:

```python
from chatgpt_bot import Conversation

>>> conversation = Conversation("some random ID", api_key="YOUR_OPENAI_API_KEY")
>>> conversation.ask("Hi, how are you today?")
"As an AI language model, I don't have feelings, but I'm always ready to assist you
with any questions or tasks you have. How can I help you today?"

>>> conversation.set_metadata({"anything": "here"})
>>> conversation.get_metadata()
{"anything": "here"}
```
