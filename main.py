#!/usr/bin/env python3

#########################################################################
# FrundenBot - A Telegram bot to watch your Freitagsrunde               #
# Copyright (C) 2018 Max Rosin                                          #
#                                                                       #
# This program is free software: you can redistribute it and/or modify  #
# it under the terms of the GNU General Public License as published by  #
# the Free Software Foundation, either version 3 of the License, or     #
# (at your option) any later version.                                   #
#                                                                       #
# This program is distributed in the hope that it will be useful,       #
# but WITHOUT ANY WARRANTY; without even the implied warranty of        #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         #
# GNU General Public License for more details.                          #
#                                                                       #
# You should have received a copy of the GNU General Public License     #
# along with this program.  If not, see <http://www.gnu.org/licenses/>. #
#########################################################################

import logging, logging.handlers
import os
import requests
import sys

from emoji import emojize
from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import CommandHandler, Filters, InlineQueryHandler, RegexHandler, MessageHandler, Updater

cache = emojize('Mist, ich weiß es nicht! :confused:', use_aliases=True)

logging.getLogger('JobQueue').setLevel(logging.INFO)
logging.getLogger('telegram').setLevel(logging.INFO)
logging.getLogger('requests').setLevel(logging.INFO)

logging_format = '[%(asctime)s: %(levelname)s/%(name)s] %(message)s'
formatter = logging.Formatter(logging_format)
logging.basicConfig(level=logging.INFO, format=logging_format)

logger = logging.getLogger('FrundenBot')
logger_fh = logging.handlers.TimedRotatingFileHandler('logs/frundenbot.log', when='midnight', backupCount=360)
logger_fh.setLevel(logging.DEBUG)
logger_fh.setFormatter(formatter)
logger.addHandler(logger_fh)

TOKEN = os.environ.get('TELEGRAM_BOT_AUTH_TOKEN')


def __log_incomming_messages(bot, update):
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
        logger.info('In:  %s: %s' % (target_chat, update.message.text))


def refresh_cache(bot, job):
    global cache
    try:
        logger.info('Refresh cache')
        r = requests.get('https://watchyour.freitagsrunde.org')
        r.raise_for_status()
        if 'Wir sind fuer dich da!' in r.text:
            cache = emojize(':white_check_mark: Die Freitagsrunde ist offen!', use_aliases=True)
        else:
            cache = emojize(':red_circle: Leider haben wir gerade zu.', use_aliases=True)
    except Exception as e:
        logger.error(e)


def start(bot, update):
    bot.sendMessage(chat_id=update.message.chat_id, text='Egal was du sagst, ich sag nur, ob die Freitagsrunde offen hat! Du kannst mich direkt anschreiben oder inline per @FrundenBot in anderen Chats benutzen.')


def inline(bot, update):
    query = update.inline_query.query
    if not query:
        return
    results = list()
    results.append(
        InlineQueryResultArticle(
            id = 0,
            title = 'Jemand da?',
            input_message_content = InputTextMessageContent(cache)
        )
    )
    logger.info('Inline Query')
    bot.answerInlineQuery(update.inline_query.id, results)


def is_open(bot, update):
    __log_incomming_messages(bot,update)
    bot.sendMessage(chat_id=update.message.chat_id, text=cache)


if __name__ == '__main__':
    updater = Updater(token=TOKEN)
    dispatcher = updater.dispatcher
    queue = updater.job_queue

    queue.run_repeating(refresh_cache, interval=60, first=0)

    start_handler = CommandHandler('start', start)
    inline_handler = InlineQueryHandler(inline)
    open_handler = CommandHandler('open', is_open)
    offen_handler = CommandHandler('offen', is_open)
    message_handler = MessageHandler(Filters.text, is_open)

    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(inline_handler)
    dispatcher.add_handler(message_handler)
    dispatcher.add_handler(open_handler)
    dispatcher.add_handler(offen_handler)

    updater.start_polling()
