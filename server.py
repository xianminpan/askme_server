#!/usr/bin/env python3

import os
import json
import uuid
import logging
import requests
from api import MessageApiClient
from event import MessageReceiveEvent, UrlVerificationEvent, EventManager
from flask import Flask, jsonify
from dotenv import load_dotenv, find_dotenv

import threading
from queue import Queue
from sparkapi import websocket_main_loop, question_q, answer_q


# load env parameters form file named .env
load_dotenv(find_dotenv(filename='../.env'))

app = Flask(__name__)

# load from env
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")
ENCRYPT_KEY = os.getenv("ENCRYPT_KEY")
LARK_HOST = os.getenv("LARK_HOST")

# init service
message_api_client = MessageApiClient(APP_ID, APP_SECRET, LARK_HOST)
event_manager = EventManager()


@event_manager.register("url_verification")
def request_url_verify_handler(req_data: UrlVerificationEvent):
    # url verification, just need return challenge
    if req_data.event.token != VERIFICATION_TOKEN:
        raise Exception("VERIFICATION_TOKEN is invalid")
    return jsonify({"challenge": req_data.event.challenge})


@event_manager.register("im.message.receive_v1")
def message_receive_event_handler(req_data: MessageReceiveEvent):
    global question_q, answer_q
    sender_id = req_data.event.sender.sender_id
    message = req_data.event.message
    if message.message_type != "text":
        logging.warn("Other types of messages have not been processed yet")
        return jsonify()
    open_id = sender_id.open_id
    text_content = message.content
    dict_content = json.loads(text_content)
    question_q.put(dict_content.get('text'))
    answer = answer_q.get()
    dict_content['text'] = answer
    text_content = json.dumps(dict_content)
    message_api_client.send_text_with_open_id(open_id, text_content)
    return jsonify()


@app.errorhandler
def msg_error_handler(ex):
    logging.error(ex)
    response = jsonify(message=str(ex))
    response.status_code = (
        ex.response.status_code if isinstance(ex, requests.HTTPError) else 500
    )
    return response


@app.route("/", methods=["POST"])
def callback_event_handler():
    # init callback instance and handle
    event_handler, event = event_manager.get_handler_with_event(VERIFICATION_TOKEN, ENCRYPT_KEY)
    return event_handler(event)


if __name__ == '__main__':
    t = threading.Thread(
            target=websocket_main_loop, 
            args=("fa2ecf52", "133a96ca621d419b88ec064db2b2c810", "YTFjZjM1YjE5MTI3YzY0MDlhMGM4NDIz", "ws://spark-api.xf-yun.com/v1.1/chat"))
    t.start()
    app.run(host="0.0.0.0", port=3000, debug=True)
    t.join()
