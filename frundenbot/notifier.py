import logging

from emoji import emojize
from telegram import Bot, ParseMode

from frundenbot import MESSAGE_OPEN, STATE_OPEN, STATE_UNKNOWN
from frundenbot.storage import Storage

LOGGER = logging.getLogger(__name__)


class Notifier:
    """
    Used to send notifications when the "open" status changes
    """

    def __init__(self, bot: Bot, storage: Storage):
        self._bot = bot
        self._storage = storage

    def register(self, chat_id: int):
        """
        Registers a chat_id to be notified
        :param chat_id: chat id
        """
        listeners = self._storage.get_notification_listeners()
        listeners.add(f"{chat_id}")
        self._storage.set_notification_listeners(listeners)

    def unregister_all(self):
        self._storage.set_notification_listeners(set())

    def on_state(self, state: int):
        """
        Listener for state changes
        :param state: new state
        """
        if state == STATE_UNKNOWN:
            return

        try:
            old_state = self._storage.get_open()
            if old_state == STATE_UNKNOWN:
                # this will only happen once for a given storage
                return
            if old_state != state:
                self._storage.set_open(state)
                if state == STATE_OPEN:
                    self._notify_all()
        finally:
            self._storage.set_open(state)

    def _notify_all(self):
        """
        Notifies all currently registered chats
        """
        for chat_id in self._storage.get_notification_listeners():
            try:
                self._bot.send_message(
                    chat_id=chat_id,
                    text=emojize(MESSAGE_OPEN, language='alias'),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                LOGGER.error(e)

        self.unregister_all()
