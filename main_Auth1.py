
import tweepy
import getpass
import pandas as pd
import re
import json
import flask
import os
import datetime
from flask import Flask, render_template_string, redirect, request, render_template


def HtmlIntake(path):
    with open(path) as f:
        lines = f.readlines()
    return ''.join(lines)

def loadWords():
    f = open("profane_words.json", 'r')
    bad_words = json.load(f)
    return bad_words


def initTwitter():
    bearer_token = os.environ['BEARER_TOKEN']
    # api = tweepy.API(bearer_token)
    # # assign the values accordingly
    # auth = tweepy.AppAuthHandler(os.environ['api_key'], os.environ['api_secret'])
    # api = api(auth)
    auth = tweepy.OAuth2BearerHandler(bearer_token)
    api = tweepy.API(auth)
    return api

def scrape_tl_username(name):
    temp_list =[]
    for status in tweepy.Cursor(api.user_timeline, screen_name=name, tweet_mode="extended").items():
        temp_list.append((status.full_text, status.created_at))
    timeline_df = pd.DataFrame(temp_list, columns=['Tweet','date_full'])
    return timeline_df

def scrape_tl(uid, count):
    """Function to collect user's timeline. UID is user ID number count is number of tweets to check. Max 32k"""
    out_text = []
    temp_list = []
    min_id = api.get_timelines(uid, max_results=5).data[0].id
    while len(out_text) < int(count):
        resp = api.get_timelines(uid, max_results=100, until_id=min_id)
        resp.data
        min_id = resp.data[-1].id
        for i in resp.data:
            out_text.append(i)
    out_text
    for item in out_text:
        temp_list.append([item.id, item.text])
    timeline_df = pd.DataFrame(temp_list, columns=['id', 'text'])
    return timeline_df


def flag_check(flag_list, text):
    flag_count = 0
    flags_found = []
    for flag in flag_list:
        if len(re.findall(f" {flag} ", text)) > 0:
            flag_count += 1
            flags_found.append(flag)
    return flags_found


def flagDFProces(df):
    df['Profane Words'] = df['Tweet'].apply(lambda x: flag_check(bad_words, x))
    df['occurance'] = df['Profane Words'].apply(lambda x: 1 if len(x)>0 else 0)
    df['Date'] = df['date_full'].apply(lambda x: datetime.datetime.date(x))
    return df

#  Per request
def main(user_id):
    df = scrape_tl_username(user_id)
    print(f"Timeline Scrape Complete {df.shape[0]} tweet's collected")
    processed_df = flagDFProces(df)
    profane_df = processed_df[processed_df.occurance == 1]
    print(f"{profane_df.shape[0]} Profane Tweets Found")
    return profane_df

def initWebsite(returnPage):
    app = Flask(__name__)

    @app.route("/", methods=['GET'])
    def home():
        return render_template_string(homePage)

    @app.route("/setUser", methods=["POST"])
    def setUser():
        user = request.form["user"]
        render_template_string(fetchTweetsPage)
        temp_df = main(user)
        p_count = str(temp_df.shape[0])
        return render_template_string(returnPage.replace('{}', p_count).replace('{text}',temp_df.to_html()))

    app.run(debug=False)


#  initialization
bad_words = loadWords()
api = initTwitter()
homePage = HtmlIntake("templates/homepage.html")
# inputPage = HtmlIntake("../Scripts/html/templates/Input.html")
fetchTweetsPage = HtmlIntake("templates/Fetching_tweets.html")
returnPage = HtmlIntake("templates/returnPage.html")
initWebsite(returnPage)
print("Initialization Complete http://127.0.0.1:5000/ ")