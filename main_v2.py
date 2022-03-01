# import pytwitter
# from pytwitter import Api
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

def flagDFProces(df):
    df['Profane Words'] = df['Tweet'].apply(lambda x: flag_check(bad_words, x))
    df['occurance'] = df['Profane Words'].apply(lambda x: 1 if len(x) > 0 else 0)
    df['Date'] = df['date_full'].apply(lambda x: datetime.datetime.date(x))
    return df

def inituserOauth():
    oauth2_user_handler = tweepy.OAuth2UserHandler(
        client_id=os.environ['CLIENT_ID'],
        redirect_uri="http://127.0.0.1:5000/return",
        scope=["tweet.read", "tweet.write", "users.read"],
        # Client Secret is only necessary if using a confidential client
        client_secret=os.environ['CLIENT_SECRET']

    )

    return oauth2_user_handler

  #  return oauth2_user_handler.get_authorization_url()



#  Per request
def main(user_id):
    #df = scrape_tl_username(user_id)

    total_count = df.shape[0]
    print(f"Timeline Scrape Complete {total_count} tweet's collected")
    processed_df = flagDFProces(df)
    profane_df = processed_df[processed_df.occurance == 1]
    print(f"{profane_df.shape[0]} Profane Tweets Found")
    return profane_df, total_count


def initWebsite(returnPage):
    app = Flask(__name__)

    oauth2_handler = inituserOauth()
    app.auth = oauth2_handler

    @app.route("/", methods=['GET'])
    def home():
        authorization_url = app.auth.get_authorization_url()
        print(authorization_url)
        return render_template_string(index.replace('{user_auth_link}',authorization_url))

    @app.route('/return')
    def results():
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        access_token = app.auth.fetch_token(request.url)
        client = tweepy.Client(access_token)
        #print(request.url)

        return render_template_string(returnPage)

    @app.route("/setUser", methods=["POST"])
    def setUser():
        user = request.form["user"]
        render_template_string(fetchTweetsPage)
        temp_df, total_count = main(user)
        p_count = str(temp_df.shape[0])
        # return render_template_string(returnPage.replace('{}', p_count).replace('{text}',temp_df.to_html()))
        return render_template_string(returnPage
                                      .replace('{p_count}', p_count)
                                      .replace('{table}', temp_df.drop(['date_full','occurance'],1).to_html())
                                      .replace('{total_count}', str(total_count))
                                      .replace('{user}', user)
                                      )

    app.run(debug=False)


#  initialization
bad_words = loadWords()
homePage = HtmlIntake("templates/homepage2.html")
fetchTweetsPage = HtmlIntake("templates/Fetching_tweets.html")
returnPage = HtmlIntake("templates/returnPage2.html")
index = HtmlIntake("templates/index.html")
initWebsite(returnPage)





