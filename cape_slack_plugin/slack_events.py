import json
from functools import wraps
from collections import deque
from typing import Optional
from uuid import uuid4

from cape_slack_plugin.slack_settings import URL_BASE
from cape_slack_plugin.slack_settings import slack_event_endpoints
from cape_slack_plugin.slack_utils import send_slack_message, get_slack_file_contents
from webservices.app.app_middleware import respond_with_json
from webservices.app.app_core import _answer as responder_answer
from webservices.app.app_saved_reply_endpoints import _create_saved_reply as responder_create_saved_reply
from webservices.app.app_saved_reply_endpoints import _add_paraphrase_question as responder_add_paraphrase_question
from webservices.app.app_document_endpoints import _upload_document as responder_upload_document
from userdb.bot import Bot
from userdb.user import User
from webservices.bots_common.utils import try_numerical_answer, NUMERICAL_EXPRESSION_THRESHOLD, NON_WORD_CHARS, \
    ERROR_HELP_MESSAGE
from api_helpers.input import required_parameter, optional_parameter
from api_helpers.text_responses import ERROR_FILE_TYPE_UNSUPPORTED, BOT_FILE_UPLOADED
from api_helpers.exceptions import UserException
import re

_endpoint_route = lambda x: slack_event_endpoints.route(URL_BASE + x, methods=['GET', 'POST'])

_processed_events = deque(maxlen=1000)
# Answer response to the last question asked, broken down by bot and channel
_previous_answers = {}
# Index of the last answer provided from _previous_answers, broken down by bot and channel
_last_answer = {}
# Echo mode
_ECHO_MODE = {}

_BOT_TS_TO_MESSAGE = {}
_BOT_MESSAGE_TO_ANSWER = {}
_LAST_QUESTION = {}


def _needs_question(wrapped):
    @wraps(wrapped)
    def decorated(bot, channel, *args):

        if bot.bot_id not in _last_answer or channel not in _last_answer[bot.bot_id]:
            send_slack_message(bot.bot_token, channel, "Please ask a question first.")
            return
        else:
            return wrapped(bot, channel, *args)

    return decorated


def _help(bot, channel, *args):
    send_slack_message(bot.bot_token, channel, """Hi, I am *Capebot*, I will answer all your questions, I will learn from you and your documents and improve over time.
Here are my commands:

    *.add* _question_ | _answer_ - Create a new saved reply.
    *.next* - Show the next possible answer for the last question.
    *.why* - Explain why the last answer was given.
    *.help* - Display this message.

You can also :

    *Add* a Slack emoji reaction to bot answers with :thumbsup: or :smiley:, I will remember and improve over time. 
    *Upload* text and markdown documents by sending them to me in a private message. I will read them when answering.
    *Ask* me to calculate, for example `what is 3+2?`.

For more options login to your account at https://thecape.ai.
    """)


def _process_bot_message_event(bot: Bot, event: dict):
    if event.get('subtype', None) != 'bot_message' or 'channel' not in event or 'ts' not in event:
        return
    _BOT_TS_TO_MESSAGE[bot.bot_id, event['channel'], event['ts']] = event['text']


def _process_answer(bot: Bot, channel: str, question: str, answer: dict):
    _BOT_MESSAGE_TO_ANSWER[bot.bot_id, channel, answer['answerText']] = {'question': question, 'answer': answer}


def _process_responder_api(bot, channel, api_endpoint, request) -> Optional[dict]:
    try:
        response = json.loads(api_endpoint(request).body)
    except UserException as e:
        send_slack_message(bot.bot_token, channel, e.message + ERROR_HELP_MESSAGE)
        return None
    if response['success']:
        return response
    else:
        send_slack_message(bot.bot_token, channel, response['result']['message'] + ERROR_HELP_MESSAGE)
        return None


def _get_question_answer(bot: Bot, channel: str, ts: str):
    if _BOT_TS_TO_MESSAGE.get((bot.bot_id, channel, ts), None):
        return _BOT_MESSAGE_TO_ANSWER.get((bot.bot_id, channel, _BOT_TS_TO_MESSAGE[bot.bot_id, channel, ts]), None)


def _remove_question_answer(bot: Bot, channel: str, ts: str):
    del _BOT_MESSAGE_TO_ANSWER[bot.bot_id, channel, _BOT_TS_TO_MESSAGE[bot.bot_id, channel, ts]]


def _get_last_answer(bot, channel):
    if bot.bot_id not in _last_answer or channel not in _last_answer[bot.bot_id]:
        return None
    return _previous_answers[bot.bot_id][channel][_last_answer[bot.bot_id][channel]]


def _add_saved_reply(bot, channel, request, message):
    try:
        if message.startswith("."):
            message = message[NON_WORD_CHARS.search(message).end():]
        question_answer = [qa.strip() for qa in message.split('|')]
        if len(question_answer) < 2:
            raise IndexError()
    except IndexError:
        send_slack_message(bot.bot_token, channel,
                           "Sorry, I didn't understand that. The usage for `.add` is: "
                           ".add question | answer")
        return

    request['user'] = User.get('user_id', bot.user_id)
    questions = question_answer[:-1]
    answer = question_answer[-1]
    request['args']['question'] = questions[0]
    request['args']['answer'] = answer
    response = _process_responder_api(bot, channel, responder_create_saved_reply, request)
    if not response:
        return
    reply_id = response['result']['replyId']
    for question in questions[1:]:
        request['args']['question'] = question
        request['args']['replyid'] = reply_id  # we do lower() for all parameters
        if not _process_responder_api(bot, channel, responder_add_paraphrase_question, request):
            return
    if len(questions) == 1:
        questions_text = f'_{questions[0]}_\n'
    else:
        questions_text = ''
        for question in questions:
            questions_text += f'•_{question}_\n'
    send_slack_message(bot.bot_token, channel,
                       f"Thanks, I'll remember that:\n{questions_text}>>>{answer}")


@_needs_question
def _next(bot, channel, *args):
    next_answer = _last_answer[bot.bot_id][channel] + 1
    if next_answer < len(_previous_answers[bot.bot_id][channel]):
        answer = _previous_answers[bot.bot_id][channel][next_answer]
        _process_answer(bot, channel, _LAST_QUESTION[bot.bot_id, channel], answer)
        response = send_slack_message(bot.bot_token, channel, answer['answerText'])
        _BOT_TS_TO_MESSAGE[bot.bot_id, channel, response['message']['ts']] = answer['answerText']
        _last_answer[bot.bot_id][channel] = next_answer
    else:
        send_slack_message(bot.bot_token, channel, "I'm afraid I've run out of answers to that question.")


@_needs_question
def _explain(bot, channel, *args):
    previous = _get_last_answer(bot, channel)
    if previous['sourceType'] == 'document':
        context = previous["answerContext"]
        local_start_offset = previous['answerTextStartOffset'] - previous['answerContextStartOffset']
        local_end_offset = previous['answerTextEndOffset'] - previous['answerContextStartOffset']
        bold_text = context[local_start_offset:local_end_offset].replace('\n', '')
        context = f"{context[:local_start_offset]} *{bold_text}* {context[local_end_offset:]}"
        send_slack_message(bot.bot_token, channel,
                           f"From _{previous['sourceId']}_ (Index {previous['confidence']:.2f})\n>>>{context}")
    else:
        send_slack_message(bot.bot_token, channel,
                           f"I thought you asked (Index {previous['confidence']:.2f})\n_{previous['matchedQuestion']}_\n>>>{previous['answerText']}")


def _process_positive_reaction(bot: Bot, request, event: dict) -> Optional[bool]:
    if event['type'] != 'reaction_added':
        return None
    if event['reaction'] not in {'smiley', 'smile', 'wink', 'simple_smile', 'grinning', 'kissing', 'laughing',
                                 'satisfied', 'thumbsup', 'ok_hand', '+1', 'v', 'point_up', 'point_up_2', 'clap',
                                 'muscle', 'raised_hands', 'arrow_up', 'up', 'ok', 'new', 'top', 'cool', '100',
                                 'heavy_check_mark', 'ballot_box_with_check', 'white_check_mark'}:
        return False
    channel = event['item']['channel']
    question_answer = _get_question_answer(bot, channel, event['item']['ts'])
    if not question_answer:
        return None
    _remove_question_answer(bot, channel, event['item']['ts'])
    question = question_answer['question']
    last_answer = question_answer['answer']
    if last_answer['sourceType'] == 'saved_reply':
        if last_answer['confidence'] == 1.0:
            send_slack_message(bot.bot_token, channel,
                               f"Thanks for the feedback.\n_{question}_\n>>>{last_answer['answerText']}")
            return True
        request['user'] = User.get('user_id', bot.user_id)
        request['args']['question'] = question.strip()
        request['args']['replyid'] = last_answer['sourceId']  # we do lower() for all parameters
        if _process_responder_api(bot, channel, responder_add_paraphrase_question, request):
            send_slack_message(bot.bot_token, channel,
                               f"Thanks, I'll remember that:\n_{question}_\n>>>{last_answer['answerText']}")
        return True
    elif last_answer['sourceType'] == 'document':
        request['user'] = User.get('user_id', bot.user_id)
        request['args']['question'] = question.strip()
        request['args']['answer'] = last_answer['answerText'].strip()
        if _process_responder_api(bot, channel, responder_create_saved_reply, request):
            send_slack_message(bot.bot_token, channel,
                               f"Thanks, I'll remember that:\n_{question}_\n>>>{last_answer['answerText']}")
        return True
    else:
        send_slack_message(bot.bot_token, channel,
                           f"Thanks for the feedback.\n_{question}_\n>>>{last_answer['answerText']}")
        return True


def _echo(bot, channel, request, message):
    if message.startswith(".echo"):
        _ECHO_MODE[bot.bot_id, channel] = not _ECHO_MODE.get((bot.bot_id, channel), False)
        send_slack_message(bot.bot_token, channel, "Echo mode toggled")
    else:
        send_slack_message(bot.bot_token, channel, message)


def _answer(bot, channel, request, question):
    user = User.get('user_id', bot.user_id)
    request['args']['token'] = user.token
    request['args']['question'] = question
    request['args']['numberofitems'] = '5'
    response = _process_responder_api(bot, channel, responder_answer, request)
    if not response:
        return
    answers = response['result']['items']
    if bot.bot_id not in _previous_answers:
        _previous_answers[bot.bot_id] = {}
        _last_answer[bot.bot_id] = {}
    _previous_answers[bot.bot_id][channel] = answers
    _last_answer[bot.bot_id][channel] = 0
    _LAST_QUESTION[bot.bot_id, channel] = question
    if not answers or answers[0]['confidence'] < NUMERICAL_EXPRESSION_THRESHOLD:
        numerical_answer = try_numerical_answer(question)
        if numerical_answer:
            answers.insert(0, {"answerText": numerical_answer[0] + "=" + numerical_answer[1],
                               "confidence": 0.80,
                               "sourceType": "numerical",
                               "sourceId": str(uuid4()),
                               "matchedQuestion": f"What is {numerical_answer[0]} ?"
                               })
    if len(answers) == 0:
        send_slack_message(bot.bot_token, channel, "Sorry! I don't know the answer to that.")
    else:
        _process_answer(bot, channel, question, answers[0])
        response = send_slack_message(bot.bot_token, channel, answers[0]['answerText'])
        _BOT_TS_TO_MESSAGE[bot.bot_id, channel, response['message']['ts']] = answers[0]['answerText']


_ACTIONS = [
    (lambda bot, channel, request, message: message.startswith(".echo") or _ECHO_MODE.get((bot.bot_id, channel), False),
     _echo),
    (lambda bot, channel, request, message: message.startswith(".add"), _add_saved_reply),
    # Included in previous condition:
    # (lambda bot, channel, request, message: message.startswith(".addSavedReply"), _add_saved_reply),
    # (lambda bot, channel, request, message: message.startswith(".add_saved_reply"), _add_saved_reply),
    # (lambda bot, channel, request, message: message.startswith(".add-saved-reply"), _add_saved_reply),
    (lambda bot, channel, request, message: "|" in message, _add_saved_reply),
    (lambda bot, channel, request, message: message.startswith(".new"), _add_saved_reply),
    (lambda bot, channel, request, message: message.startswith(".help"), _help),
    (lambda bot, channel, request, message: message.startswith(".man"), _help),
    (lambda bot, channel, request, message: message.startswith(".next"), _next),
    (lambda bot, channel, request, message: message.startswith(".more"), _next),
    (lambda bot, channel, request, message: message.startswith(".explain"), _explain),
    (lambda bot, channel, request, message: message.startswith(".why"), _explain),
    (lambda bot, channel, request, message: message.startswith(".context"), _explain),
    (lambda bot, channel, request, message: message.startswith(".conf"), _explain),
    (lambda bot, channel, request, message: message.startswith(".score"), _explain),
    (lambda bot, channel, request, message: message.startswith(".index"), _explain),
    (lambda bot, channel, request, message: True, _answer),
]


def process_message(bot: Bot, event, request):
    if 'subtype' in event:
        if event['subtype'] in {'bot_message', 'file_mention'}:
            # Don't reply to private messages from our self or other bots, don't reply to file_mentions
            return "200 OK"
        elif event['subtype'] == 'file_share':
            process_file(event, request)
            return
        elif event['subtype'] == 'message_changed':
            event['text'] = event['message']['text']

    if 'text' not in event:
        return
    channel = event['channel']
    message = event['text'].replace("<@%s>" % bot.bot_id, "").strip()
    message = re.sub("<mailto:[^|]*\|([^>]*)>", r"\1", message).strip()
    for checker, action in _ACTIONS:
        try:
            checked = checker(bot, channel, request, message)
        except Exception:
            checked = False
        if checked:
            action(bot, channel, request, message)
            break


def process_tokens_revoked(event):
    if 'bot' in event['tokens']:
        for bot_id in event['tokens']['bot']:
            bot = Bot.get('bot_id', bot_id)
            bot.delete_instance()


def process_file(event, request):
    authed_users = required_parameter(request, 'authed_users')
    bot_id = authed_users[0]
    channel = event['channel']
    bot = Bot.get('bot_id', bot_id)
    slack_file = event['file']
    if slack_file['filetype'] not in ['text', 'markdown']:
        send_slack_message(bot.bot_token, channel, ERROR_FILE_TYPE_UNSUPPORTED)
    else:
        text = get_slack_file_contents(bot.bot_token, slack_file['url_private'])
        try:
            request['user'] = User.get('user_id', bot.user_id)
            request['args']['text'] = text
            request['args']['title'] = slack_file['title']
            request['args']['origin'] = slack_file['name']
            request['args']['replace'] = 'true'
            responder_upload_document(request)
            send_slack_message(bot.bot_token, channel, BOT_FILE_UPLOADED)
        except UserException as e:
            send_slack_message(bot.bot_token, channel, e.message)


@_endpoint_route('/events/receive-event')
@respond_with_json
def receive_event(request):
    challenge = optional_parameter(request, 'challenge', None)
    if challenge is not None:
        # Slack sends us a 'challenge' token when configuring the URL which we have to send back to confirm that we're
        # willing to receive events.
        return challenge
    event = required_parameter(request, 'event')
    event_id = required_parameter(request, 'event_id')
    if event_id in _processed_events:
        # We've already processed this event
        return "200 OK"
    _processed_events.append(event_id)
    bot: Bot = Bot.get('bot_id', required_parameter(request, 'authed_users')[0])
    _process_bot_message_event(bot, event)
    if _process_positive_reaction(bot, request, event):
        return "200 OK"
    if event['type'] == 'message' or event['type'] == 'app_mention' and 'subtype' not in event:
        process_message(bot, event, request)
    elif event['type'] == 'tokens_revoked':
        process_tokens_revoked(event)
    return "200 OK"
