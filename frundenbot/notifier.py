from emoji import emojize
from telegram import ParseMode

from frundenbot import STATE_OPEN, STATE_UNKNOWN, MESSAGE_OPEN


class Notifier:
    """
    Used to send notifications when the "open" status changes
    """

    # set of chat_ids that have registered for a notification
    chat_ids = set()
    # the last
    last_known_state = STATE_UNKNOWN

    def __init__(self, bot):
        self._bot = bot

    def register(self, chat_id: str):
        """
        Registers a chat_id to be notified
        :param chat_id: chat id
        """
        self.chat_ids.add(chat_id)

    def on_state(self, state: int):
        """
        Listener for state changes
        :param state: new state
        """
        if state == STATE_UNKNOWN:
            return

        if self.last_known_state == STATE_UNKNOWN:
            self.last_known_state = state
            return

        if self.last_known_state != state == STATE_OPEN:
            self._notify_all()

    def _notify_all(self):
        """
        Notifies all currently registered chats
        """
        for chat_id in self.chat_ids:
            self._bot.send_message(
                chat_id=chat_id,
                text=emojize(MESSAGE_OPEN, use_aliases=True),
                parse_mode=ParseMode.MARKDOWN
            )
        self.chat_ids.clear()
