import tweepy
import pandas as pd
import re
import json
import os
import datetime
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, BaseLoader
from dotenv import load_dotenv

app = FastAPI()
templates = Jinja2Templates(directory='templates')


def HtmlIntake(path):
    with open(path) as f:
        lines = f.readlines()
    return ''.join(lines)


def loadWords():
    f = open("profane_words.json", 'r')
    bad_words = json.load(f)
    bad_words_pattern = ' | '.join(bad_words)
    return bad_words_pattern, bad_words


def flagDFProces(df):
    df['Profane Words'] = df['Text'].apply(lambda x: re.findall(bad_words_pattern, x))
    df['occurance'] = df['Profane Words'].apply(lambda x: 1 if len(x) > 0 else 0)
    df['Date'] = df['date_full'].apply(lambda x: datetime.datetime.date(x))
    return df


def inituserOauth():
    oauth2_user_handler = tweepy.OAuth2UserHandler(
        client_id=os.getenv('CLIENT_ID'),
        redirect_uri="http://127.0.0.1:5000/return",
        scope=["tweet.read", "tweet.write", "users.read"],
        # Client Secret is only necessary if using a confidential client
        client_secret=os.getenv('CLIENT_SECRET'))

    return oauth2_user_handler


oauth2_handler = inituserOauth()
app.auth = oauth2_handler

index = HtmlIntake("templates/index.html")

@app.get("/")
async def home(request: Request):
    authorization_url = app.auth.get_authorization_url()

    return Environment.from_string(index).render({"request": request})
   # return templates.TemplateResponse('index.html', {"request": request})
