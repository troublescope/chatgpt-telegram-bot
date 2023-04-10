import datetime as dt
import unittest
from telegram import Chat, Message, Update, User
from telegram.constants import ChatType
from telegram.ext import CallbackContext

from bot import askers
from bot import bot
from bot.bot import Filters
from bot.config import config
from bot import models
from tests.mocks import FakeGPT, FakeApplication, FakeBot


class PrivateChatTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ai = FakeGPT()
        askers.TextAsker.model = self.ai
        self.bot = FakeBot("bot")
        self.chat = Chat(id=1, type=ChatType.PRIVATE)
        self.chat.set_bot(self.bot)
        self.application = FakeApplication(self.bot)
        self.application.user_data[1] = {}
        self.context = CallbackContext(self.application, chat_id=1, user_id=1)
        self.user = User(id=1, first_name="Alice", is_bot=False, username="alice")
        config.telegram.usernames = ["alice"]

    async def test_start(self):
        update = self._create_update(11)
        await bot.start_handle(update, self.context)
        self.assertTrue(self.bot.text.startswith("Hi! I'm a humble AI-driven chat bot."))

    async def test_start_unknown(self):
        user = User(id=2, first_name="Bob", is_bot=False, username="bob")
        message = Message(
            message_id=11,
            date=dt.datetime.now(),
            chat=self.chat,
            from_user=user,
        )
        message.set_bot(self.bot)
        update = Update(update_id=11, message=message)
        await bot.start_handle(update, self.context)
        self.assertTrue(self.bot.text.startswith("Sorry, I don't know you"))

    async def test_retry(self):
        user_data = models.UserData(self.context.user_data)
        user_data.messages.add("What is your name?", "My name is AI.")
        update = self._create_update(11)
        await bot.retry_handle(update, self.context)
        self.assertEqual(self.bot.text, "What is your name?")

    async def test_message(self):
        update = self._create_update(11, text="What is your name?")
        await bot.message_handle(update, self.context)
        self.assertEqual(self.bot.text, "What is your name?")
        self.assertEqual(self.ai.question, "What is your name?")
        self.assertEqual(self.ai.history, [])

    async def test_follow_up(self):
        update = self._create_update(11, text="What is your name?")
        await bot.message_handle(update, self.context)
        self.assertEqual(self.ai.question, "What is your name?")
        self.assertEqual(self.ai.history, [])

        update = self._create_update(12, text="+ And why is that?")
        await bot.message_handle(update, self.context)
        self.assertEqual(self.ai.question, "And why is that?")
        self.assertEqual(self.ai.history, [("What is your name?", "What is your name?")])

        update = self._create_update(13, text="+ Where are you?")
        await bot.message_handle(update, self.context)
        self.assertEqual(self.ai.question, "Where are you?")
        self.assertEqual(
            self.ai.history,
            [
                ("What is your name?", "What is your name?"),
                ("+ And why is that?", "And why is that?"),
            ],
        )

    async def test_forward(self):
        update = self._create_update(11, text="What is your name?", forward_date=dt.datetime.now())
        await bot.message_handle(update, self.context)
        self.assertTrue(self.bot.text.startswith("This is a forwarded message"))

    async def test_document(self):
        update = self._create_update(11, text="I have so much to say" + "." * 5000)
        await bot.message_handle(update, self.context)
        self.assertEqual(self.bot.text, "I have so much to... (see attachment for the rest): 11.md")

    async def test_exception(self):
        askers.TextAsker.model = FakeGPT(error=Exception("connection timeout"))
        update = self._create_update(11, text="What is your name?")
        await bot.message_handle(update, self.context)
        self.assertTrue(self.bot.text.startswith("Failed to answer"))
        self.assertTrue("connection timeout" in self.bot.text)

    async def test_error(self):
        self.context.error = Exception("Something went wrong")
        update = self._create_update(11, "Something went wrong")
        update._effective_chat = self.chat
        await bot.error_handler(update, self.context)
        self.assertEqual(self.bot.text, "⚠️ Something went wrong")

    def _create_update(self, update_id: int, text: str = None, **kwargs) -> Update:
        message = Message(
            message_id=update_id,
            date=dt.datetime.now(),
            chat=self.chat,
            text=text,
            from_user=self.user,
            **kwargs,
        )
        message.set_bot(self.bot)
        return Update(update_id=update_id, message=message)


class GroupChatTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        askers.TextAsker.model = FakeGPT()
        self.bot = FakeBot("bot")
        self.chat = Chat(id=1, type=ChatType.GROUP)
        self.chat.set_bot(self.bot)
        self.application = FakeApplication(self.bot)
        self.application.user_data[1] = {}
        self.application.user_data[2] = {}
        self.context = CallbackContext(self.application, chat_id=1, user_id=1)
        self.user_alice = User(id=1, first_name="Alice", is_bot=False, username="alice")
        self.user_erik = User(id=2, first_name="Erik", is_bot=False, username="erik")
        self.user_bot = User(id=42, first_name="Bot", is_bot=True, username="bot")
        config.telegram.usernames = ["alice"]

    async def test_message(self):
        update = self._create_update(11, text="@bot What is your name?")
        await bot.message_handle(update, self.context)
        self.assertEqual(self.bot.text, "What is your name?")

    async def test_no_mention(self):
        update = self._create_update(11, text="What is your name?")
        await bot.message_handle(update, self.context)
        self.assertEqual(self.bot.text, "")

    def _create_update(self, update_id: int, text: str = None, **kwargs) -> Update:
        message = Message(
            message_id=update_id,
            date=dt.datetime.now(),
            chat=self.chat,
            text=text,
            from_user=self.user_alice,
            **kwargs,
        )
        message.set_bot(self.bot)
        return Update(update_id=update_id, message=message)


class ConfigTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ai = FakeGPT()
        askers.TextAsker.model = self.ai
        self.bot = FakeBot("bot")
        self.chat = Chat(id=1, type=ChatType.PRIVATE)
        self.chat.set_bot(self.bot)
        self.application = FakeApplication(self.bot)
        self.application.user_data[1] = {}
        self.context = CallbackContext(self.application, chat_id=1, user_id=1)
        self.user = User(id=1, first_name="Alice", is_bot=False, username="alice")
        config.telegram.usernames = ["alice"]
        config.telegram.admins = ["alice"]
        Filters.init()

    async def test_help(self):
        update = self._create_update(11, "/config")
        await bot.config_handle(update, self.context)
        self.assertTrue(self.bot.text.startswith("Syntax:"))

    async def test_view(self):
        config.openai.model = "gpt-3.5-turbo"
        update = self._create_update(11, "/config openai.model")
        await bot.config_handle(update, self.context)
        self.assertEqual(self.bot.text, "`gpt-3.5-turbo`")

    async def test_change(self):
        config.save = lambda: None
        config.openai.model = "gpt-3.5-turbo"
        update = self._create_update(11, "/config openai.model gpt-4")
        await bot.config_handle(update, self.context)
        self.assertTrue(self.bot.text.startswith("✓ Changed the `openai.model` property"))

    async def test_not_changed(self):
        config.save = lambda: None
        config.openai.model = "gpt-3.5-turbo"
        update = self._create_update(11, "/config openai.model gpt-3.5-turbo")
        await bot.config_handle(update, self.context)
        self.assertEqual(
            self.bot.text, "✗ The `openai.model` property already equals to `gpt-3.5-turbo`"
        )

    async def test_delayed(self):
        config.save = lambda: None
        config.max_history_depth = 3
        update = self._create_update(11, "/config max_history_depth 5")
        await bot.config_handle(update, self.context)
        self.assertTrue("Restart the bot" in self.bot.text)

    async def test_telegram_usernames(self):
        update = self._create_update(11, '/config telegram.usernames ["alice", "bob"]')
        await bot.config_handle(update, self.context)
        self.assertEqual(Filters.user.usernames, frozenset(["alice", "bob"]))

    async def test_telegram_admins(self):
        update = self._create_update(11, '/config telegram.admins ["alice", "bob"]')
        await bot.config_handle(update, self.context)
        self.assertEqual(Filters.admin.usernames, frozenset(["alice", "bob"]))

    async def test_telegram_chat_ids(self):
        update = self._create_update(11, "/config telegram.chat_ids [-100500]")
        await bot.config_handle(update, self.context)
        self.assertEqual(Filters.chat.chat_ids, frozenset([-100500]))

    def _create_update(self, update_id: int, text: str = None, **kwargs) -> Update:
        message = Message(
            message_id=update_id,
            date=dt.datetime.now(),
            chat=self.chat,
            text=text,
            from_user=self.user,
            **kwargs,
        )
        message.set_bot(self.bot)
        return Update(update_id=update_id, message=message)
