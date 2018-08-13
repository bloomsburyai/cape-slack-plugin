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
