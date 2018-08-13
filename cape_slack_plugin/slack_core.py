import requests
from typing import Union
from sanic import Sanic
from cape_slack_plugin.slack_settings import slack_endpoints
from cape_slack_plugin.slack_auth import slack_auth_endpoints
from cape_slack_plugin.slack_events import slack_event_endpoints
from webservices.configuration.configuration_core import configuration_endpoints
from webservices.errors.errors_core import errors_endpoints
from logging import debug
from cape_slack_plugin import slack_settings

app = Sanic(__name__)
app.blueprint(slack_endpoints)
app.blueprint(slack_auth_endpoints)
app.blueprint(slack_event_endpoints)
app.blueprint(configuration_endpoints)
app.blueprint(errors_endpoints)
app.static('/', file_or_directory=slack_settings.STATIC_FOLDER)
app.static('/', file_or_directory=slack_settings.HTML_INDEX_STATIC_FILE)
app.config.update(slack_settings.WEBAPP_CONFIG)


def run(port: Union[None, int] = None):
    if port is not None:
        slack_settings.CONFIG_SERVER['port'] = int(port)
    debug("Using port", slack_settings.CONFIG_SERVER['port'])
    app.run(**slack_settings.CONFIG_SERVER)
