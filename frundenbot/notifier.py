from emoji import emojize
from telegram import ParseMode, Bot

from frundenbot import STATE_OPEN, STATE_UNKNOWN, MESSAGE_OPEN
from frundenbot.storage import Storage


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
        listeners.append(f"{chat_id}")
        self._storage.set_notification_listeners(listeners)

    def unregister_all(self):
        self._storage.set_notification_listeners([])

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
            self._bot.send_message(
                chat_id=chat_id,
                text=emojize(MESSAGE_OPEN, use_aliases=True),
                parse_mode=ParseMode.MARKDOWN
            )
        self.unregister_all()
