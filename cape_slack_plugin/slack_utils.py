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


def send_slack_message(token, channel, text):
    slack_request = requests.Session()
    response = slack_request.post('https://slack.com/api/chat.postMessage', params={
        'token': token,
        'channel': channel,
        'text': text
    })
    slack_request.close()
    return response.json()


def fetch_slack_file_info(token, file_id):
    slack_request = requests.Session()
    response = slack_request.post('https://slack.com/api/files.info', params={
        'token': token,
        'file_id': file_id
    })
    slack_request.close()
    return response.json()


def add_slack_file_comment(token, file_id, text):
    slack_request = requests.Session()
    slack_request.post('https://slack.com/api/files.comments.add', params={
        'token': token,
        'file_id': file_id,
        'comment': text
    })
    slack_request.close()


def get_slack_file_contents(token, url):
    slack_request = requests.Session()
    text = slack_request.get(url, headers={'Authorization': 'Bearer %s' % token}).text
    slack_request.close()
    return text
