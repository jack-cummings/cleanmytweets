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
    bad_words_pattern =' | '.join(bad_words)
    return bad_words_pattern, bad_words


def flagDFProces(df):
    df['Profane Words'] = df['Text'].apply(lambda x: re.findall(bad_words_pattern,x))
    df['occurance'] = df['Profane Words'].apply(lambda x: 1 if len(x) > 0 else 0)
    df['Date'] = df['date_full'].apply(lambda x: datetime.datetime.date(x))
    return df

def inituserOauth():
    oauth2_user_handler = tweepy.OAuth2UserHandler(
        client_id=os.environ['CLIENT_ID'],
        redirect_uri="http://127.0.0.1:5000/return",
        scope=["tweet.read", "tweet.write", "users.read"],
        # Client Secret is only necessary if using a confidential client
        client_secret=os.environ['CLIENT_SECRET'])

    return oauth2_user_handler


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
        client = tweepy.Client(access_token['access_token'])

        user = client.get_me(user_auth=False)
        username= user.data.username
        user_id = user.data.id

        tweets_out=[]
        for tweet in tweepy.Paginator(client.get_users_tweets, id=user_id,
                                      tweet_fields=['id', 'text', 'created_at'], max_results=100).flatten(limit=300):

            tweets_out.append([tweet.id, tweet.text, tweet.created_at])

        timeline_df = pd.DataFrame(tweets_out, columns=['Delete?', 'Text', 'date_full'])
        tweet_count = timeline_df.shape[0]
        app.df = timeline_df
        app.user = username
        app.client = client

        return render_template_string(tweetCountPage.replace('{tweet_count}', str(tweet_count)))

    @app.route("/scan_tweets", methods=["POST","GET"])
    def scan_tweets():
        df = app.df
        total_count = df.shape[0]
        out_df = flagDFProces(df)
        prof_df = out_df[out_df['occurance']==1]

        check_box = r"""<input type="checkbox" id="\1" name="tweet_id" value="\1">
                                <label for="\1">  </label><br>"""
        out_table_html = re.sub(r'(\d{18})', check_box, prof_df.drop(['date_full', 'occurance'], 1).to_html(index= False).replace('<td>', '<td align="center">'))
        p_count = prof_df.shape[0]

        return render_template_string(returnPage
                                      .replace('{p_count}', str(p_count))
                                      .replace('{table}', out_table_html)
                                      .replace('{total_count}', str(total_count))
                                      .replace('{user}', app.user)
                                      )

    @app.route("/selectTweets", methods=["POST"])
    def selectTweets():
        values = request.form.getlist("tweet_id")
        if len(values) < 50:
            for v in values:
                app.client.delete_tweet(v, user_auth=False)
        else:
            return (over50Page)

        return render_template_string(tweetsDeletedPage.replace('{count}', str(len(values))))

    app.run(debug=False)


#  initialization
bad_words_pattern, bad_words = loadWords()
homePage = HtmlIntake("templates/homepage2.html")
fetchTweetsPage = HtmlIntake("templates/Fetching_tweets.html")
returnPage = HtmlIntake("templates/returnPage2.html")
index = HtmlIntake("templates/index.html")
tweetCountPage = HtmlIntake("templates/tweet_count.html")
tweetsDeletedPage = HtmlIntake("templates/Tweets_deleted.html")
over50Page = HtmlIntake("templates/over50Page.html")
initWebsite(returnPage)





