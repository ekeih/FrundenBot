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
                          InlineQueryHandler, MessageHandler, RegexHandler,
                          Updater)
from telegram_click import generate_command_list
from telegram_click.decorator import command

cache = emojize('Sorry, ich weiß es nicht! :confused:', use_aliases=True)

logging.getLogger('JobQueue').setLevel(logging.INFO)
logging.getLogger('telegram').setLevel(logging.INFO)
logging.getLogger('requests').setLevel(logging.INFO)

logging_format = '[%(asctime)s: %(levelname)s/%(name)s] %(message)s'
logging.basicConfig(level=logging.INFO, format=logging_format)

LOGGER = logging.getLogger(__name__)

ADMIN = int(os.environ.get('TELEGRAM_BOT_ADMIN'))
LIST_OF_ADMINS = [int(x)
                  for x in os.environ.get('TELEGRAM_BOT_ADMINS').split(',')]


class FrundenBot:
    def __init__(self, token, refresh_interval):

        self.FRUNDE_OPEN = Gauge(
            'frunde_status', '1 if Frunde is open,-1 on error, 0 otherwise')

        updater = Updater(token=token, use_context=True)
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
                                text='{}\nÜbrigens kannst du mit /mate nachgucken, ob es noch Getränke gibt.'.format(cache))

    WHOAMI_TIME = Summary('frunde_whoami_seconds',
                          'Time spent executing /whoami handler')

    @WHOAMI_TIME.time()
    def _callback_whoami(self, update: Update, context: CallbackContext):
        context.bot.sendMessage(chat_id=update.message.chat_id, text='You are: {} ({})'.format(
            update.message.from_user.name, update.message.chat_id))
        LOGGER.info('This is: {} ({})'.format(
            update.message.from_user.name, update.message.chat_id))

    GET_DRINKS_TIME = Summary(
        'frunde_get_drinks_seconds', 'Time spent executing /mate (/drinks) handler')

    @GET_DRINKS_TIME.time()
    @command(name=['mate', 'drinks'], description='Are there drinks available at the Freitagsrunde?')
    def _callback_get_drinks(self, update: Update, context: CallbackContext):
        try:
            with open('/var/frunde/frunde_drinks.txt', 'r') as file:
                drinks = file.read()
        except Exception as e:
            drinks = emojize(
                'Uhm, das weiß ich nicht. :confused:', use_aliases=True)
            LOGGER.error(e)
        context.bot.sendMessage(chat_id=update.message.chat_id, text=drinks)

    SET_DRINKS = Summary('frunde_set_drinks_seconds',
                         'Time spent executing /set_mate handler')

    @SET_DRINKS.time()
    def _callback_set_drinks(self, update: Update, context: CallbackContext):
        if update.message.chat_id in LIST_OF_ADMINS:
            mate_message = ' '.join(context.args)
            LOGGER.info('New mate message: {}'.format(mate_message))
            try:
                with open('/var/frunde/frunde_drinks.txt', 'w+') as file:
                    file.write('{}\n(Aktualisiert: {})'.format(
                        mate_message, time.strftime('%d.%m.%Y um %H:%M')))
                    result = 'Neuer Matepegel:\n{}'.format(mate_message)
            except Exception as e:
                result = emojize(
                    'Uhm, das hat nicht geklappt. :confused:', use_aliases=True)
                LOGGER.error(e)
            context.bot.sendMessage(
                chat_id=update.message.chat_id, text=result)
            context.bot.sendMessage(chat_id=ADMIN, text='Neuer Matepegel von {} ({}):\n{}'.format(
                update.message.from_user.name, update.message.chat_id, result))
        else:
            context.bot.sendMessage(chat_id=update.message.chat_id, text=emojize(
                ':poop: Nö :poop:', use_aliases=True))

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
            if 'Wir sind fuer dich da!' in r.text:
                self.FRUNDE_OPEN.set(1)
                cache = emojize(
                    ':white_check_mark: Die Freitagsrunde ist offen!', use_aliases=True)
            else:
                self.FRUNDE_OPEN.set(0)
                cache = emojize(
                    ':red_circle: Leider haben wir gerade zu.', use_aliases=True)
        except Exception as e:
            self.FRUNDE_OPEN.set(-1)
            cache = emojize(
                'Sorry, ich weiß es nicht! :confused:', use_aliases=True)
            LOGGER.error(e)


@click.command()
@click.option('--token', envvar='FRUNDE_TOKEN', help='Telegram bot token.', required=True)
@click.option('--refresh-interval', envvar='FRUNDE_REFRESH_INTERVAL', default=60, help='Interval in seconds in which the bot should check if the Freitagsrunde is open.', show_default=True)
@click.option('--metrics-port', envvar='FRUNDE_METRICS_PORT', default=8000, help='Port to expose Prometheus metrics.', show_default=True)
def cli(token, refresh_interval: int, metrics_port: int):
    """
    All options are also available as environment variables, e.g. "--refresh-interva=30" can be set by "export REFRESH_INTERVAL=30".
    """
    start_http_server(metrics_port)
    FrundenBot(token=token, refresh_interval=refresh_interval)
