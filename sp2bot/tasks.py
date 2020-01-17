#!/usr/bin/env python
# -*- coding: utf-8 -*-

from telegram.error import BadRequest
from telegram.ext import CallbackContext

from sp2bot import store
from sp2bot.message import Message
from sp2bot.splatoon2 import Splatoon2


class Task:

    def __init__(self, job_queue=None):
        self._battle_pools = []
        self.job_queue = job_queue

    def task_exist(self, user_id):
        return self.get_job(user_id) is not None

    def get_job(self, user_id):
        # print(f'Query job with user_id: {user_id}')
        # print([j.name for j in self.job_queue.jobs()])

        all_jobs = self.job_queue.jobs()
        jobs = [j for j in all_jobs if j.name == str(user_id) and not j.removed]
        # print('Not removed jobs:')
        # print([j.name for j in jobs])
        if jobs and len(jobs) > 0:
            return jobs[0]
        return None

    def stop_push(self, user_id):
        job = self.get_job(user_id)
        if job:
            job.schedule_removal()

        store.update_push_to_false(user_id)

    def load_and_run_all_push_job(self):
        for battle_poll in store.get_started_push_poll():
            self.start_battle_push(battle_poll)

    def start_battle_push(self, battle_poll):
        if self.task_exist(battle_poll.user.id):
            return

        # Update poll to database
        store.update_battle_poll(battle_poll)

        self._battle_pools.append(battle_poll)

        job_params = (battle_poll,
                      Splatoon2(battle_poll.user.iksm_session))
        self.job_queue.run_repeating(self._battle_push_task,
                                     interval=10,
                                     first=0,
                                     context=job_params,
                                     name=str(battle_poll.user.id))

    def _battle_push_task(self, context: CallbackContext):
        (battle_poll, splatoon2) = context.job.context

        last_message_id = battle_poll.last_message_id
        last_battle_number = battle_poll.last_battle_number
        bot = context.bot

        # Get last battle detail
        battle_overview = splatoon2.get_battle_overview()
        if len(battle_overview.results) == 0:
            return
        last_battle = battle_overview.results[0]

        print(last_battle.battle_number)
        if last_battle_number and \
                last_battle_number != last_battle.battle_number:

            battle = splatoon2.get_battle(last_battle.battle_number)

            # Update stat
            battle_poll.game_count += 1
            battle_poll.game_victory_count += int(battle.victory)
            battle_poll.last_battle_number = last_battle.battle_number
            # Save updated to context
            context.job.context = (battle_poll, splatoon2)

            # Send push message
            (content, message_type) = Message.push_battle(battle,
                                                          battle_poll)
            parse_mode = message_type if message_type else None

            try:
                sent_message = bot.send_message(battle_poll.chat.id,
                                                content,
                                                parse_mode=parse_mode)
            except BadRequest as e:
                # Resend
                sent_message = bot.send_message(battle_poll.chat.id, content)

            # Update value
            battle_poll.last_message_id = sent_message.message_id
            # Save updated to context
            context.job.context = (battle_poll, splatoon2)

            # Delete
            if last_message_id:
                bot.delete_message(battle_poll.chat.id, last_message_id)

        elif not last_battle_number:
            battle_poll.last_battle_number = last_battle.battle_number
            # Save updated to context
            context.job.context = (battle_poll, splatoon2)

        store.update_battle_poll(battle_poll)
