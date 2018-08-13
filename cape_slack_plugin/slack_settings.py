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

from sanic import Blueprint
import os

URL_BASE = '/slack'
slack_auth_endpoints = Blueprint('slack_auth_endpoints')
slack_event_endpoints = Blueprint('slack_event_endpoints')

slack_client_id = os.getenv("CAPE_SLACK_CLIENT_ID", "REPLACEME")
slack_client_secret = os.getenv("CAPE_SLACK_CLIENT_SECRET", "REPLACEME")
slack_verification = os.getenv("CAPE_SLACK_VERIFICATION", "REPLACEME")
slack_app_url = os.getenv("CAPE_SLACK_APP_URL", "REPLACEME")

THIS_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__)))
