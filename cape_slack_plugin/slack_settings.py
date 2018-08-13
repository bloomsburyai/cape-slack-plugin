from sanic import Blueprint
import os

URL_BASE = '/slack'
slack_endpoints = Blueprint('slack_endpoints')
slack_auth_endpoints = Blueprint('slack_auth_endpoints')
slack_event_endpoints = Blueprint('slack_event_endpoints')

slack_client_id = os.getenv("CAPE_SLACK_CLIENT_ID", "REPLACEME")
slack_client_secret = os.getenv("CAPE_SLACK_CLIENT_SECRET", "REPLACEME")
slack_verification = os.getenv("CAPE_SLACK_VERIFICATION", "REPLACEME")
slack_app_url = os.getenv("CAPE_SLACK_APP_URL", "REPLACEME")

THIS_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__)))
