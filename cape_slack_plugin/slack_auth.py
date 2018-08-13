# Copyright 2018 BLEMUNDSBURY AI LIMITED
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import requests
from sanic.response import redirect
from cape_slack_plugin.slack_settings import URL_BASE
from cape_slack_plugin.slack_settings import slack_auth_endpoints, slack_client_id, slack_client_secret, \
    slack_app_url
from webservices.app.app_middleware import requires_auth
from userdb.bot import Bot
from api_helpers.exceptions import UserException
from api_helpers.input import required_parameter
from api_helpers.text_responses import *
from peewee import IntegrityError

_endpoint_route = lambda x: slack_auth_endpoints.route(URL_BASE + x, methods=['GET', 'POST'])


@_endpoint_route('/auth/oauth_callback')
@requires_auth
def oauth_callback(request):
    oauth_code = required_parameter(request, "code")
    slack_request = requests.Session()
    slack_response = slack_request.get("https://slack.com/api/oauth.access",
                                       params={"client_id": slack_client_id,
                                               "client_secret": slack_client_secret,
                                               "code": oauth_code})
    slack_request.close()
    try:
        bot = Bot(user_id=request['user'].user_id,
                  bot_id=slack_response.json()['bot']['bot_user_id'],
                  bot_token=slack_response.json()['bot']['bot_access_token'],
                  access_token=slack_response.json()['access_token'])
        bot.save()
    except KeyError:
        raise UserException(ERROR_INVALID_SLACK_RESPONSE)
    except IntegrityError:
        # We already have this bot, so update it with new tokens
        bot = Bot.get('bot_id', slack_response.json()['bot']['bot_user_id'])
        bot.user_id = request['user'].user_id
        bot.bot_token = slack_response.json()['bot']['bot_access_token']
        bot.access_token = slack_response.json()['access_token']
        bot.save()
        return redirect('https://thecape.ai/slack.html#complete')
    return redirect('https://thecape.ai/slack.html#complete')
