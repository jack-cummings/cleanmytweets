import tweepy
import pandas as pd
import re
import json
import os
import datetime
import stripe
import time
from fastapi import FastAPI, Request, BackgroundTasks, Response, Cookie
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse


## Configs
if os.environ['MODE'] == 'dev':
    import uvicorn

    stripe.api_key = os.environ['STRIPE_KEY_DEV']
    price = "price_1KeQ1PCsKWtKuHp0PIYQ1AnH"
else:
    stripe.api_key = os.environ['STRIPE_KEY_DEV']
    price = "price_1KeQ1PCsKWtKuHp0PIYQ1AnH"

if os.environ['PAY_MODE'] == 'pay':
    return_path = "create-checkout-session"
else:
    return_path = 'free_mode'


def HtmlIntake(path):
    with open(path) as f:
        lines = f.readlines()
    return ''.join(lines)


def loadWords(mode):
    f = open("references/profane_words.json", 'r')
    bad_words = json.load(f)
    bad_words_pattern = ' | '.join(bad_words)
    return bad_words_pattern, bad_words


def flagDFProces(df):
    df['Profane Words'] = df['Text'].apply(lambda x: ' , '.join(re.findall(bad_words_pattern, x)))
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
        #basepath = "https://www.cleanmytweets.com"
        basepath = 'https://cleanmytweets.herokuapp.com'

    return basepath


def getTweets(user_id, response, client):
    # Collect user timeline
    twitter_client = client
    tweets_out = []
    for tweet in tweepy.Paginator(twitter_client.get_users_tweets, id=user_id,
                                  tweet_fields=['id', 'text', 'created_at'], max_results=100).flatten(limit=3000):
        tweets_out.append([tweet.id, tweet.text, tweet.created_at])

    timeline_df = pd.DataFrame(tweets_out, columns=['Delete?', 'Text', 'date_full'])

    # Run scan for flag words
    out_df = flagDFProces(timeline_df)

    total_count = out_df.shape[0]
    prof_df = out_df[out_df['occurance'] == 1]
    prof_df['Text'] = prof_df['Text'].apply(lambda x: x.encode('utf-8', 'ignore'))

    check_box = r"""<input type="checkbox" id="\1" name="tweet_id" value="\1">
                            <label for="\1">  </label><br>"""
    out_table_html = str(re.sub(r'(\d{18,19})', check_box,
                                prof_df.drop(['date_full', 'occurance'], 1).to_html(index=False).replace(
                                    '<td>', '<td align="center">').replace(
                                    '<tr style="text-align: right;">', '<tr style="text-align: center;">').replace(
                                    '<table border="1" class="dataframe">', '<table class="table">')))

    p_count = prof_df.shape[0]

    # Set output cookies
    response.set_cookie(key="total_count", value=total_count)
    response.set_cookie(key="table", value=out_table_html)
    response.set_cookie(key="p_count", value=p_count)


#  initialization
mode = os.environ['MODE']
bad_words_pattern, bad_words = loadWords(mode)

app = FastAPI()
basepath = setBasePath(mode)
oauth2_handler = inituserOauth(basepath)
app.auth = oauth2_handler
templates = Jinja2Templates(directory='templates/jinja')

@app.get("/")
async def home(request: Request):
    try:
        authorization_url = app.auth.get_authorization_url()
        return templates.TemplateResponse('index_j.html', {"request": request, "user_auth_link": authorization_url})
    except:
        return templates.TemplateResponse('error.html', {"request": request})


@app.get('/return')
async def results(request: Request, background_tasks: BackgroundTasks, response: Response):
    try:
        access_token = app.auth.fetch_token(str(request.url))
        client = tweepy.Client(access_token['access_token'])
    except:
        return templates.TemplateResponse('auth_failed.html', {"request": request})

    user = client.get_me(user_auth=False)
    username = user.data.username
    user_id = user.data.id
    # app.user_id = user_id
    # app.user = username
    # app.client = client
    response.set_cookie(key="user_id", value=user_id)
    response.set_cookie(key="user", value=username)
    #response.set_cookie(key="client", value=client)

    # Begin Timeline scrape
    print(f'beginning scrape: {username}')
    background_tasks.add_task(getTweets, user_id=user_id, response=response, client=client)

    return templates.TemplateResponse('account_val.html', {"request": request, "user": username,
                                                           "return_path": return_path})

@app.get("/success")
async def success(request: Request):
    return templates.TemplateResponse('payment_val.html', {"request": request, "user": Cookie('user')})

@app.get("/free_mode")
async def success(request: Request):
    return templates.TemplateResponse('free_mode.html', {"request": request})


@app.get('/create-checkout-session')
async def create_checkout_session(request: Request):
    checkout_session = stripe.checkout.Session.create(
        success_url=basepath + "/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=basepath,
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price": price,
            "quantity": 1
        }],
    )
    return RedirectResponse(checkout_session.url, status_code=303)


@app.get("/scan_tweets")
async def scan_tweets(request: Request):
    p_count = Cookie('p_count')
    table = Cookie('table')
    total_count = Cookie('total_count')
    try:
        return templates.TemplateResponse('returnPage_j.html', {"request": request,
                                                                "p_count": str(p_count),
                                                                'table': table,
                                                                'total_count': str(total_count),
                                                                'user': Cookie('user')})
    except:
        return templates.TemplateResponse('error.html', {"request": request})


@app.post('/selectTweets')
async def selectTweets(request: Request):
    try:
        body = await request.body()
        values = body.decode("utf-8").replace('tweet_id=', '').split(',')
        if values == [""]:
            pass
        elif len(values) < 17:
            delete_failed_flag = False
            for v in values:
                try:
                    twitter_client = Cookie('client')
                    twitter_client.delete_tweet(v, user_auth=False)
                except:
                    delete_failed_flag = True
            if delete_failed_flag:
                return templates.TemplateResponse('delete_failed.html', {'request': request})
            else:
                return templates.TemplateResponse('Tweets_deleted.html', {'request': request,
                                                                          'count': str(len(values))})
        elif len(values) >= 17:
            return templates.TemplateResponse('over_15.html', {'request': request})

    except:
        return templates.TemplateResponse('error.html', {"request": request})

if __name__ == '__main__':
    if os.environ['MODE'] == 'dev':
        uvicorn.run(app, port=5050, host='0.0.0.0')
