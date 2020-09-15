#!/usr/bin/env python
# -*- coding: utf-8 -*-
import configs
from sp2bot.api import API, APIAuthError
from telegram.bot import log


class SP2BattleAPI(API):

    def __init__(self):
        super(SP2BattleAPI, self).__init__()
        self._base_url = configs.IMINK_API_URL
        self._headers = {'X-Access-Token': configs.SP2BATTLE_API_TOKEN}

    @log
    def get_client_token(self, user_id, iksm_session, sp2_principal_id):
        try:
            data = self.get(
                f'/client_token?telegram_id={user_id}&'
                f'iksm_session={iksm_session}&'
                f'sp2_principal_id={sp2_principal_id}'
            )
            if data['code'] == 0:
                return data['data']
            else:
                return None
        except:
            return None

    @log
    def reset_client_token(self, user_id, iksm_session, sp2_principal_id):
        try:
            data = self.post(f'/reset_client_token',
                             data={
                                 'telegram_id': user_id,
                                 'iksm_session': iksm_session,
                                 'sp2_principal_id': sp2_principal_id
                             })
            if data['code'] == 0:
                return data['data']
            else:
                return None
        except:
            return None
