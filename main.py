import tweepy
import pandas as pd
import re
import json
import os
import datetime
import stripe
from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

if os.environ['MODE'] == 'dev':
    import uvicorn


def HtmlIntake(path):
    with open(path) as f:
        lines = f.readlines()
    return ''.join(lines)


def loadWords(mode):
    if mode == 'dev':
        f = open("references/profane_words.json", 'r')
    else:
        f = open("profane_words.json", 'r')
    bad_words = json.load(f)
    bad_words_pattern = ' | '.join(bad_words)
    return bad_words_pattern, bad_words


def flagDFProces(df):
    df['Profane Words'] = df['Text'].apply(lambda x: re.findall(bad_words_pattern, x))
    df['occurance'] = df['Profane Words'].apply(lambda x: 1 if len(x) > 0 else 0)
    df['Date'] = df['date_full'].apply(lambda x: datetime.datetime.date(x))
    return df


def inituserOauth(basepath):
    oauth2_user_handler = tweepy.OAuth2UserHandler(
        client_id=os.getenv('CLIENT_ID'),
        redirect_uri=f'{basepath}/return',
        scope=["tweet.read", "tweet.write", "users.read"],
        # Client Secret is only necessary if using a confidential client
        client_secret=os.getenv('CLIENT_SECRET'))

    return oauth2_user_handler


def setBasePath(mode):
    if mode.lower() == 'dev':
        basepath = 'http://0.0.0.0:5050'
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    elif mode.lower() == 'prod':
        basepath = "https://www.cleanmytweets.com"

    return basepath


#  initialization
mode = os.environ['MODE']
bad_words_pattern, bad_words = loadWords(mode)

app = FastAPI()
basepath = setBasePath(mode)
oauth2_handler = inituserOauth(basepath)
app.auth = oauth2_handler
templates = Jinja2Templates(directory='templates/jinja')
app.mount('/static', StaticFiles(directory='static'), name='static')
stripe.api_key = 'sk_test_51KdgypCsKWtKuHp0d9jyiwQkvw0IEFdMtiAqjyYyHKsZlAAsktTCFAnWNfmfVqzvXhtFrH0saw3s2hDjwSzsbAVc00dPdysxhW'


@app.get("/")
async def home(request: Request):
    authorization_url = app.auth.get_authorization_url()
    return templates.TemplateResponse('index_j.html', {"request": request, "user_auth_link": authorization_url})


@app.get('/return')
async def results(request: Request):
    access_token = app.auth.fetch_token(str(request.url))
    client = tweepy.Client(access_token['access_token'])

    user = client.get_me(user_auth=False)
    username = user.data.username
    user_id = user.data.id
    app.user_id = user_id
    app.user = username
    app.client = client

    return templates.TemplateResponse('account_val.html', {"request": request, "user": username})


@app.get("/success")
async def success(request: Request):
    return templates.TemplateResponse('success.html', {"request": request})


@app.get("/cancel")
async def cancel(request: Request):
    return templates.TemplateResponse('cancel.html', {"request": request})



@app.get('/create-checkout-session')
async def create_checkout_session(request: Request):

    checkout_session = stripe.checkout.Session.create(
        success_url=basepath+"/scan_tweets?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=basepath,
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price": "price_1KeQ1PCsKWtKuHp0PIYQ1AnH",
            "quantity": 1
        }],
    )
    return RedirectResponse(checkout_session.url, status_code=303)


@app.get("/scan_tweets")
async def scan_tweets(request: Request):
    # Get Tweets
    tweets_out = []
    for tweet in tweepy.Paginator(app.client.get_users_tweets, id=app.user_id,
                                  tweet_fields=['id', 'text', 'created_at'], max_results=100).flatten(limit=3000):
        tweets_out.append([tweet.id, tweet.text, tweet.created_at])

    timeline_df = pd.DataFrame(tweets_out, columns=['Delete?', 'Text', 'date_full'])
    df = timeline_df

    total_count = df.shape[0]
    out_df = flagDFProces(df)
    prof_df = out_df[out_df['occurance'] == 1]

    check_box = r"""<input type="checkbox" id="\1" name="tweet_id" value="\1">
                            <label for="\1">  </label><br>"""
    out_table_html = str(re.sub(r'(\d{18,19})', check_box,
                                prof_df.drop(['date_full', 'occurance'], 1).to_html(index=False).replace(
                                    '<td>','<td align="center">').replace(
                                    '<tr style="text-align: right;">', '<tr style="text-align: center;">')))
    p_count = prof_df.shape[0]

    return templates.TemplateResponse('returnPage_j.html', {"request": request,
                                                            "p_count": str(p_count),
                                                            'table': out_table_html,
                                                            'total_count': str(total_count),
                                                            'user': app.user})


@app.post('/selectTweets')
async def selectTweets(request: Request):
    body = await request.body()
    values = body.decode("utf-8").replace('tweet_id=', '').split(',')
    if values == [""]:
        pass
    elif len(values) < 50:
        for v in values:
            app.client.delete_tweet(v, user_auth=False)
    else:
        return templates.TemplateResponse('over50Page.html', {'request': request})

    return templates.TemplateResponse('Tweets_deleted.html', {'request': request,
                                                              'count': str(len(values))})


if __name__ == '__main__':
    if os.environ['MODE'] == 'dev':
        uvicorn.run(app, port=5050, host='0.0.0.0')
