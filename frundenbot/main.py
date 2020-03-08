#!/usr/bin/env python3

# FrundenBot - A Telegram bot to watch your Freitagsrunde
# Copyright (C) 2018 Max Rosin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
import os
import sys
import time

import click
import requests
from emoji import emojize
from prometheus_client import Gauge, Summary, start_http_server
from telegram import (InlineQueryResultArticle, InputTextMessageContent,
                      ParseMode, Update)
from telegram.ext import (CallbackContext, CommandHandler, Filters,
                          InlineQueryHandler, MessageHandler, Updater)
from telegram_click import generate_command_list
from telegram_click.decorator import command

from frundenbot import STATE_CLOSED, STATE_OPEN, STATE_UNKNOWN, MESSAGE_OPEN
from frundenbot.notifier import Notifier
from frundenbot.storage import Storage

cache = emojize('Sorry, ich weiß es nicht! :confused:', use_aliases=True)

logging.getLogger('JobQueue').setLevel(logging.INFO)
logging.getLogger('telegram').setLevel(logging.INFO)
logging.getLogger('requests').setLevel(logging.INFO)

logging_format = '[%(asctime)s: %(levelname)s/%(name)s] %(message)s'
logging.basicConfig(level=logging.INFO, format=logging_format)

LOGGER = logging.getLogger(__name__)

LIST_OF_ADMINS = [
    int(x) for x in os.environ.get('TELEGRAM_BOT_ADMINS').split(',')
]


class FrundenBot:
    def __init__(self, token, refresh_interval, storage: Storage):

        self.storage = storage
        self.FRUNDE_OPEN = Gauge(
            'frunde_status', '1 if Frunde is open,-1 on error, 0 otherwise')

        updater = Updater(token=token, use_context=True)

        self.notifier = Notifier(updater.bot, storage)

        dispatcher = updater.dispatcher
        queue = updater.job_queue
        queue.run_repeating(self.refresh_cache,
                            interval=refresh_interval, first=0)
        me = dispatcher.bot.get_me()
        LOGGER.info('Running as %s (%s)', me.username, me.id)

        handler_groups = {
            0: [MessageHandler(None, callback=self._callback_log_message)],
            1: [
                InlineQueryHandler(callback=self._callback_inline),
                CommandHandler(['help', 'h'], callback=self._callback_help),
                CommandHandler('start', callback=self._callback_start),
                CommandHandler(['open', 'offen'],
                               callback=self._callback_is_open),
                CommandHandler(['mate', 'drinks'],
                               callback=self._callback_get_drinks),
                CommandHandler('notify', callback=self._callback_notify),
                CommandHandler('whoami', callback=self._callback_whoami),
                CommandHandler('set_mate', callback=self._callback_set_drinks),
                MessageHandler(Filters.text, callback=self._callback_is_open)
            ]
        }

        for group, handlers in handler_groups.items():
            for handler in handlers:
                dispatcher.add_handler(handler, group=group)

        updater.start_polling()
        updater.idle()

    LOG_TIME = Summary('frunde_log_seconds',
                       'Time spent logging incomming message')

    @LOG_TIME.time()
    def _callback_log_message(self, update: Update, context: CallbackContext):
        chat = update.message.chat
        target_chat = ''
        if chat.type == 'group':
            target_chat = chat.title
        elif chat.type == 'private':
            if chat.first_name:
                target_chat += chat.first_name
            if chat.last_name:
                target_chat += ' %s' % chat.last_name
            if chat.username:
                target_chat += ' (%s)' % chat.username
        LOGGER.info('In:  %s: %s' % (target_chat, update.message.text))

    START_TIME = Summary('frunde_start_seconds',
                         'Time spent executing /start handler')

    @START_TIME.time()
    def _callback_start(self, update: Update, context: CallbackContext):
        context.bot.sendMessage(chat_id=update.message.chat_id,
                                text='Egal was du sagst, ich sag nur, ob die Freitagsrunde offen hat! Du kannst mich direkt anschreiben oder inline per @FrundenBot in anderen Chats benutzen.')

    @command(name=['help', 'h'], description='List of commands supported by this bot.')
    def _callback_help(self, update: Update, context: CallbackContext):
        text = generate_command_list(update, context)
        context.bot.send_message(
            chat_id=update.message.chat_id, text=text, parse_mode=ParseMode.MARKDOWN)

    OPEN_TIME = Summary('frunde_open_seconds',
                        'Time spent executing /open handler')

    @OPEN_TIME.time()
    @command(name='open', description='Is the Freitagsrunde open right now?')
    def _callback_is_open(self, update: Update, context: CallbackContext):
        context.bot.sendMessage(chat_id=update.message.chat_id,
                                text='{}\nÜbrigens kannst du mit /mate nachgucken, ob es noch Getränke gibt.'.format(
                                    cache))

    NOTIFY_TIME = Summary('notify_seconds',
                          'Time spent executing /notify handler')

    @NOTIFY_TIME.time()
    @command(name='notify', description='Get a notification when the Freitagsrunde opens up')
    def _callback_notify(self, update: Update, context: CallbackContext):
        chat_id = update.effective_chat.id
        self.notifier.register(chat_id)
        context.bot.sendMessage(
            chat_id=update.message.chat_id,
            text=emojize(
                "Wir benachrichtigen dich, sobald die Freitagsrunde wieder geöffnet hat :mailbox_with_mail:",
                use_aliases=True)
        )

    WHOAMI_TIME = Summary('frunde_whoami_seconds', 'Time spent executing /whoami handler')

    @WHOAMI_TIME.time()
    def _callback_whoami(self, update: Update, context: CallbackContext):
        context.bot.sendMessage(chat_id=update.message.chat_id,
                                text='You are: {} ({})'.format(
                                    update.message.from_user.name, update.message.chat_id))
        LOGGER.info('This is: {} ({})'.format(
            update.message.from_user.name, update.message.chat_id))

    GET_DRINKS_TIME = Summary(
        'frunde_get_drinks_seconds', 'Time spent executing /mate (/drinks) handler')

    @GET_DRINKS_TIME.time()
    @command(name=['mate', 'drinks'], description='Are there drinks available at the Freitagsrunde?')
    def _callback_get_drinks(self, update: Update, context: CallbackContext):
        try:
            drinks = self.storage.get_mate()
            if drinks is None:
                raise AssertionError("No mate value in storage")
        except Exception as e:
            drinks = emojize(
                'Uhm, das weiß ich nicht. :confused:', use_aliases=True)
            LOGGER.error(e)
        context.bot.sendMessage(chat_id=update.message.chat_id, text=drinks)

    SET_DRINKS = Summary('frunde_set_drinks_seconds',
                         'Time spent executing /set_mate handler')

    @SET_DRINKS.time()
    def _callback_set_drinks(self, update: Update, context: CallbackContext):
        if update.message.chat_id not in LIST_OF_ADMINS:
            context.bot.sendMessage(chat_id=update.message.chat_id, text=emojize(
                ':poop: Nö :poop:', use_aliases=True))
            return

        mate_message = ' '.join(context.args)
        LOGGER.info('New mate message: {}'.format(mate_message))
        try:
            self.storage.set_mate('{}\n(Aktualisiert: {})'.format(mate_message, time.strftime('%d.%m.%Y um %H:%M')))
            result = 'Neuer Matepegel:\n{}'.format(mate_message)
        except Exception as e:
            result = emojize(
                'Uhm, das hat nicht geklappt. :confused:', use_aliases=True)
            LOGGER.error(e)
        context.bot.sendMessage(
            chat_id=update.message.chat_id, text=result)
        for admin in LIST_OF_ADMINS:
            context.bot.sendMessage(chat_id=admin,
                                    text='Neuer Matepegel von {} ({}):\n{}'.format(
                                        update.message.from_user.name,
                                        update.message.chat_id, result))

    INLINE_TIME = Summary('frunde_inline_seconds',
                          'Time spent executing inline handler')

    @INLINE_TIME.time()
    def _callback_inline(self, update: Update, context: CallbackContext):
        query = update.inline_query.query
        if not query:
            return
        results = list()
        results.append(
            InlineQueryResultArticle(
                id=0,
                title='Jemand da?',
                input_message_content=InputTextMessageContent(cache)
            )
        )
        LOGGER.info('Inline Query')
        context.bot.answerInlineQuery(update.inline_query.id, results)

    CACHE_REFRESH_TIME = Summary(
        'frunde_cache_refresh_seconds', 'Time spent refreshing cache')

    @CACHE_REFRESH_TIME.time()
    def refresh_cache(self, context: CallbackContext):
        global cache
        try:
            LOGGER.debug('Refresh cache')
            r = requests.get('https://watchyour.freitagsrunde.org')
            r.raise_for_status()
            state = self._extract_state(r.text)
            if state == STATE_OPEN:
                cache = emojize(MESSAGE_OPEN, use_aliases=True)
            else:
                cache = emojize(
                    ':red_circle: Leider haben wir gerade zu.', use_aliases=True)
        except Exception as e:
            state = STATE_UNKNOWN
            cache = emojize(
                'Sorry, ich weiß es nicht! :confused:', use_aliases=True)
            LOGGER.error(e)

        self.FRUNDE_OPEN.set(state)
        self.notifier.on_state(state)

    @staticmethod
    def _extract_state(text) -> int:
        """
        Extracts the "open state" from the given text
        :param text: text from watchyour.freitagsrunde
        :return: state
        """
        if 'Wir sind fuer dich da!' in text:
            return STATE_OPEN
        else:
            return STATE_CLOSED


@click.command()
@click.option('--token', envvar='FRUNDE_TOKEN', help='Telegram bot token.', required=True)
@click.option('--refresh-interval', envvar='FRUNDE_REFRESH_INTERVAL', default=60,
              help='Interval in seconds in which the bot should check if the Freitagsrunde is open.', show_default=True)
@click.option('--s3-region-name', envvar='FRUNDE_S3_REGION_NAME', help='Region name of the s3 bucket.')
@click.option('--s3-bucket', envvar='FRUNDE_S3_BUCKET', help='Name of the s3 bucket.')
@click.option('--s3-key', envvar='FRUNDE_S3_KEY', help='Key ID of the S3 user.')
@click.option('--s3-secret', envvar='FRUNDE_S3_SECRET', help='Secret of the S3 user.')
@click.option('--file-path', envvar='FRUNDE_FILE_PATH', default='/var/frunde/',
              help='Path to store local data, if S3 is not used.')
@click.option('--metrics-port', envvar='FRUNDE_METRICS_PORT', default=8000, help='Port to expose Prometheus metrics.',
              show_default=True)
def cli(token, refresh_interval: int, s3_region_name: str, s3_bucket: str, s3_key: str, s3_secret: str, file_path: str,
        metrics_port: int):
    """
    All options are also available as environment variables, e.g. "--refresh-interval=30" can be set by "export REFRESH_INTERVAL=30".
    """

    if s3_region_name and s3_bucket and s3_key and s3_secret:
        from frundenbot.storage import S3Storage
        storage = S3Storage(region_name=s3_region_name, bucket=s3_bucket, key=s3_key, secret=s3_secret)
    elif s3_region_name or s3_bucket or s3_key or s3_secret:
        LOGGER.error('Either all S3 settings need to be specified or none.')
        sys.exit(1)
    else:
        from frundenbot.storage import FileStorage
        storage = FileStorage(path=file_path)

    start_http_server(metrics_port)
    FrundenBot(token=token, refresh_interval=refresh_interval, storage=storage)


if __name__ == '__main__':
    cli()
