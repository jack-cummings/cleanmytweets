
import tweepy
import pandas as pd
import re
import json
import os
import datetime
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
#import uvicorn

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
        #redirect_uri="http://127.0.0.1:8080/return",
        redirect_uri= 'http://0.0.0.0:5050/return',
        #5000
        scope=["tweet.read", "tweet.write", "users.read"],
        # Client Secret is only necessary if using a confidential client
        client_secret=os.getenv('CLIENT_SECRET'))

    return oauth2_user_handler

#  initialization
bad_words_pattern, bad_words = loadWords()

app = FastAPI()
oauth2_handler = inituserOauth()
app.auth = oauth2_handler
templates = Jinja2Templates(directory='templates/jinja')


@app.get("/")
async def home(request: Request):
    authorization_url = app.auth.get_authorization_url()
    return templates.TemplateResponse('index_j.html', {"request": request, "user_auth_link": authorization_url})

@app.route('/return')
async def results(request: Request):
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    access_token = app.auth.fetch_token(str(request.url))
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

    return templates.TemplateResponse('tweet_count_j.html',{"request": request, "tweet_count": str(tweet_count)})

@app.route("/scan_tweets")
async def scan_tweets(request: Request):
    df = app.df
    total_count = df.shape[0]
    out_df = flagDFProces(df)
    prof_df = out_df[out_df['occurance']==1]

    check_box = r"""<input type="checkbox" id="\1" name="tweet_id" value="\1">
                            <label for="\1">  </label><br>"""
    out_table_html = str(re.sub(r'(\d{18})', check_box, prof_df.drop(['date_full', 'occurance'], 1).to_html(index= False).replace('<td>', '<td align="center">')))
    p_count = prof_df.shape[0]

    return templates.TemplateResponse('returnPage_j.html', {"request": request,
                                                            "p_count": str(p_count),
                                                             'table': out_table_html,
                                                             'total_count':str(total_count),
                                                              'user': app.user})

@app.route('/selectTweets')
async def selectTweets(request: Request):
    values = request.form.getlist("tweet_id")
    if len(values) < 50:
        for v in values:
            app.client.delete_tweet(v, user_auth=False)
    else:
        return templates.TemplateResponse('over50Page.html', {'request':request})

    return templates.TemplateResponse('tweetsDeletedPage.html', {'request': request,
                                                                 'count': str(len(values))})
#
# if __name__ == '__main__':
#     uvicorn.run(app, port=5050, host='0.0.0.0')