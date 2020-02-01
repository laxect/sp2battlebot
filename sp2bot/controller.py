#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re

from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

from sp2bot.botcontext import BotContext
from sp2bot.botdecorator import handler, check_session_handler
from sp2bot.message import Message, MessageType
from sp2bot.models import BattlePoll
from sp2bot.splatoon2 import Splatoon2, Splatoon2SessionInvalid, Splatoon2Auth
from sp2bot import store
from sp2bot.utils.type import try_to_int


class Controller:

    def __init__(self, task):
        self._task = task
        pass

    @handler
    def get_token(self, context):
        message = Message(context)

        login_url = Splatoon2Auth().get_login_url(context.user.id)
        if not login_url:
            context.send_message(message.splatoon_connect_error)
            return

        context.send_message(message.login_url(login_url))

    @handler
    def generate_iksm(self, context):
        message = Message(context)

        token_data = context.args[0]
        wait_message_id = context.send_message(message.generate_iksm_wait)

        session_token_code = re.search('de=(.*)&', token_data)
        session_token = Splatoon2Auth().get_session_token(context.user.id,
                                                          session_token_code.group(
                                                              1))
        if not session_token:
            context.send_message(message.splatoon_connect_error)
            return

        iksm_session = Splatoon2Auth(session_token).get_cookie(session_token)
        if not iksm_session:
            context.send_message(message.splatoon_connect_error)
            return

        context.edit_message(message.iksm_session(iksm_session),
                             wait_message_id)

    @handler
    def set_session(self, context):
        message = Message(context)
        first_set = True

        if context.message.chat.type != 'private':
            context.send_message(message.setsession_must_private_message)
            return

        args = context.args
        if len(args) != 1:
            context.send_message(message.setsession_error)
            return

        session = context.args[0]
        sp2_user = Splatoon2(session).get_user()
        if not sp2_user:
            context.send_message(message.setsession_set_fail)
            return

        user = context.user
        if user and user.iksm_session:
            first_set = False

        user.iksm_session = session
        user.sp2_user = sp2_user.player

        if first_set:
            store.insert_user(user)
        else:
            store.update_user(user)

        if first_set:
            context.send_message(message.setsession_set_success)
        else:
            context.send_message(message.setsession_update_success)

    @check_session_handler
    def last(self, context):
        args = context.args
        message = Message(context)
        splatoon2 = Splatoon2(context.user.iksm_session)

        if len(args) > 0:
            index = try_to_int(args[0])
            if len(args) > 1 or not index or index < 0 or index > 49:
                context.send_message(message.last_command_error)
                return

        try:
            battle_overview = splatoon2.get_battle_overview()
        except Splatoon2SessionInvalid:
            context.send_message(message.session_invalid)
            return

        if not battle_overview or len(battle_overview.results) == 0:
            context.send_message(message.not_found_battle)
            return

        if len(args) == 0:
            last_battle = battle_overview.results[0]
        else:
            index = int(args[0])
            if index >= len(battle_overview.results):
                context.send_message(message.not_found_battle)
                return

            last_battle = battle_overview.results[index]

        battle = splatoon2.get_battle(last_battle.battle_number)
        context.send_message(message.last_battle(battle))

    @check_session_handler
    def last50(self, context):
        message = Message(context)
        splatoon2 = Splatoon2(context.user.iksm_session)

        try:
            battle_overview = splatoon2.get_battle_overview()
        except Splatoon2SessionInvalid:
            context.send_message(message.session_invalid)
            return

        context.send_message(message.last50_overview(battle_overview))

    @check_session_handler
    def start_push(self, context):
        self._start_or_restart_push(context)

    def _start_or_restart_push(self, context):
        message = Message(context)

        # job_queue
        job = self._task.get_job(context.user.id)
        if job:
            if job.context[0].chat.id == context.chat.id:
                context.send_message(message.already_started)
                return

            battle_poll, _ = job.context

            self._task.stop_push(context.user.id)
            self._task.start_battle_push(battle_poll)

            context.send_message(message.push_here)
        else:
            battle_poll = BattlePoll(context.user, context.chat)
            self._task.start_battle_push(battle_poll)

            context.send_message(message.started)

    @check_session_handler
    def stop_push(self, context):
        message = Message(context)

        if not self._task.task_exist(context.user.id):
            context.send_message(message.already_stopped)
            return

        # Stop push
        self._task.stop_push(context.user.id)

        context.send_message(message.stopped)

    @check_session_handler
    def reset_push(self, context):
        message = Message(context)

        # job_queue
        job = self._task.get_job(context.user.id)
        if not job:
            context.send_message(message.have_not_start_push)
            return

        battle_poll, _ = job.context
        battle_poll.last_message_id = None
        battle_poll.game_count = 0
        battle_poll.game_victory_count = 0

        self._task.stop_push(context.user.id)
        self._task.start_battle_push(battle_poll)

        context.send_message(message.reset_push_success)

    @handler
    def help(self, context):
        context.send_message(Message(context).help)

    @handler
    def start(self, context):
        context.send_message('Todo')

    def menu_actions(self, update, context):
        bot = context.bot
        query = update.callback_query
        chat_id = query.message.chat.id
        user_id = query.from_user.id
        message_id = query.message.message_id
        menus = query.message.reply_markup

        context = BotContext(update, context)
        message = Message(context)

        command = query.data.split('/')
        data = command[0]

        if data == 'battle_like':
            tql_button = menus.inline_keyboard[0][0]
            tql_text = tql_button.text
            tql_text = tql_text.replace('👍', '')
            if tql_text != '':
                count = int(tql_text)
                count += 1
            else:
                count = 1
            tql_button.text = f'👍{count}'
            menus.inline_keyboard[0][0] = tql_button

            # Reset last_message_id
            job = self._task.get_job(user_id)
            (battle_poll, splatoon2) = job.context
            if battle_poll.last_message_id == message_id:
                battle_poll.last_message_id = 0
                job.context = (battle_poll, splatoon2)

            # Update reply markup
            query.edit_message_reply_markup(menus)

        if data == 'battle_more':
            battle_id = command[1]

            battle = Splatoon2(context.user.iksm_session).get_battle(battle_id)
            message = Message.push_battle_more_detail(battle)

            reply_markup = InlineKeyboardMarkup([[menus.inline_keyboard[0][0]]])

            query.edit_message_text(message[0],
                                    parse_mode=MessageType.Markdown,
                                    reply_markup=reply_markup)
            # query.edit_message_reply_markup(reply_markup)
