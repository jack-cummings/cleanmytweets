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
from typing import Optional
from sqlalchemy import create_engine

## Configs
if os.environ['MODE'] == 'dev':
    import uvicorn

if os.environ['STRIPE_MODE'] == 'prod':
    stripe.api_key = os.environ['STRIPE_KEY_PROD']
    price = "price_1L0We3CsKWtKuHp02UYDbhBF"
else:
    stripe.api_key = os.environ['STRIPE_KEY_DEV']
    price = "price_1KeQ1PCsKWtKuHp0PIYQ1AnH"


# if os.environ['PAY_MODE'] == 'pay':
#     return_path = "create-checkout-session"
# else:
#     return_path = 'free_mode'


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
        redirect_uri=f'{basepath}/return-get',
        scope=["tweet.read", "tweet.write", "users.read"],
        # Client Secret is only necessary if using a confidential client
        client_secret=os.getenv('CLIENT_SECRET'))

    return oauth2_user_handler


def setBasePath(mode):
    if mode.lower() == 'dev':
        basepath = 'http://0.0.0.0:4242'
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    elif mode.lower() == 'prod':
        basepath = "https://www.cleanmytweets.com"
        # basepath = 'https://cleanmytweets.herokuapp.com'

    return basepath


def getTweets(user_id, client, username):
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
    prof_df = pd.DataFrame(out_df[out_df['occurance'] == 1])
    prof_df['Text'] = prof_df['Text'].apply(lambda x: x.encode('utf-8', 'ignore'))

    prof_df['username'] = username
    prof_df['total_count'] = total_count

    # Check length of prof_df
    if len(prof_df) == 0:
        prof_df.loc[1] = [0, "Great work, we've found no controversial tweets in your timeline!",
                          datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S+00:00'), ' ', 1,
                          datetime.datetime.now().strftime('%Y-%m-%d'), username, 0]

    user_df = pd.DataFrame([[username, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S+00:00')]],
                           columns=['Name', 'Insert_DT'])

    # write to sql
    prof_df.to_sql('tweets', con=db_engine, if_exists='append')  # 'replace'
    user_df.to_sql('users', con=db_engine, if_exists='append')

    print('Processing Complete')


#  initialization
mode = os.environ['MODE']
bad_words_pattern, bad_words = loadWords(mode)
# init DB
db_engine = create_engine(os.environ['DB_URL'], echo=False)

app = FastAPI()
basepath = setBasePath(mode)
templates = Jinja2Templates(directory='templates/jinja')


@app.get("/")
async def home(request: Request):
    try:
        global oauth2_handler
        oauth2_handler = inituserOauth(basepath)
        authorization_url = oauth2_handler.get_authorization_url()
        return templates.TemplateResponse('index_j.html', {"request": request, "user_auth_link": authorization_url})


    except Exception as e:
        print(e)
        return templates.TemplateResponse('error.html', {"request": request})


@app.get('/return-get', response_class=RedirectResponse)

async def results(request: Request, background_tasks: BackgroundTasks):
    try:
        access_token = oauth2_handler.fetch_token(str(request.url))
        print(2)
        client = tweepy.Client(access_token['access_token'])
    except Exception as e:
        print(e)
        print(request.url)
        return templates.TemplateResponse('auth_failed.html', {"request": request})

    user = client.get_me(user_auth=False)
    username = user.data.username
    user_id = user.data.id
    # response.set_cookie(key="user_id", value=user_id)
    response = RedirectResponse(url="/return-get_2")
    response.set_cookie("username", str(username))
    response.set_cookie(key="access_token", value=access_token['access_token'])

    # Begin Timeline scrape
    print(f'beginning scrape: {username}')
    background_tasks.add_task(getTweets, user_id=user_id, client=client, username=username)

    return response


@app.get('/return-get_2')
async def results(request: Request, username: Optional[str] = Cookie(None)):
    return templates.TemplateResponse('account_val.html', {"request": request, "user": username,
                                                           "pc_msg": ''})


@app.post("/checkout")
async def userInput(request: Request, username: Optional[str] = Cookie(None)):
    try:
        # Collect User Input
        body = await request.body()
        inputPC = body.decode('UTF-8').split('=')[1].strip()
        approvedPCs = os.environ['PROMO_CODES'].split(',')
        halfPCS = os.environ['HALF_PROMO_CODES'].split(',')

        # Check if promocode entered
        if len(inputPC) > 0:

            # if full proce promo, no checkout
            if inputPC in approvedPCs:
                return templates.TemplateResponse('payment_val.html', {"request": request, "user": Cookie('user')})

            # if half-price promo, checkout with default price overwritten
            elif inputPC in halfPCS:
                checkout_session = stripe.checkout.Session.create(
                    success_url=basepath + "/success?session_id={CHECKOUT_SESSION_ID}",
                    cancel_url=basepath,
                    payment_method_types=["card"],
                    mode="payment",
                    line_items=[{
                        "price": 'price_1KdhRoCsKWtKuHp0EfcqdUG8',
                        "quantity": 1
                    }], )
                return RedirectResponse(checkout_session.url, status_code=303)

            # If promocode invalid, return error window
            else:
                return templates.TemplateResponse('account_val.html', {"request": request, "user": username,
                                                                       "pc_msg": 'Incorrect promocode. Please try again.'})

        # If no promocode, then full price stripe checkout
        else:
            checkout_session = stripe.checkout.Session.create(
                success_url=basepath + "/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=basepath,
                payment_method_types=["card"],
                mode="payment",
                line_items=[{
                    "price": price,
                    "quantity": 1
                }], )
            return RedirectResponse(checkout_session.url, status_code=303)

    except Exception as e:
        print(e)
        return templates.TemplateResponse('error.html', {"request": request})


@app.get("/success")
async def success(request: Request):
    return templates.TemplateResponse('payment_val.html', {"request": request, "user": Cookie('user')})


@app.get("/free_mode")
async def success(request: Request):
    return templates.TemplateResponse('free_mode.html', {"request": request})


@app.get("/learn_more")
async def read(request: Request, response: Response, ):
    return templates.TemplateResponse('learn_more.html', {"request": request})


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
async def scan_tweets(request: Request, username: Optional[str] = Cookie(None)):
    # pull rows
    query = (f"""
            SELECT * 
            FROM tweets
            WHERE username = '{username}'""")

    df = pd.read_sql_query(query, db_engine)

    # delete from DB
    db_engine.execute(f"DELETE FROM tweets WHERE username = '{username}'")

    try:
        df['Text'] = df['Text'].apply(lambda x: bytes.fromhex(x[2:]).decode('utf-8'))
    except ValueError:
        pass

    df = df.drop_duplicates()
    check_box = r"""<input type="checkbox" id="\1" name="tweet_id" value="\1">
                            <label for="\1">  </label><br>"""
    out_table_html = str(re.sub(r'(\d{18,19})', check_box,
                                df.drop(columns=['date_full', 'occurance', 'username', 'total_count', 'index'],
                                        axis=1).to_html(index=False).replace(
                                    '<td>', '<td align="center">').replace(
                                    '<tr style="text-align: right;">', '<tr style="text-align: center;">').replace(
                                    '<table border="1" class="dataframe">', '<table class="table">')))

    return templates.TemplateResponse('returnPage_j.html', {"request": request,
                                                            "p_count": str(df.shape[0]),
                                                            'table': out_table_html,
                                                            'total_count': str(df['total_count'].values[0]),
                                                            'user': username})
    try:
        tc = str(df['total_count'].values[0])
    except:
        tc = str(0)

    try:
        return templates.TemplateResponse('returnPage_j.html', {"request": request,
                                                                "p_count": str(df.shape[0]),
                                                                'table': out_table_html,
                                                                'total_count': tc,
                                                                'user': Cookie('user')})
    except Exception as e:
        print(e)
        return templates.TemplateResponse('error.html', {"request": request})


@app.post('/selectTweets')
async def selectTweets(request: Request, access_token: Optional[str] = Cookie(None)):
    try:
        client = tweepy.Client(access_token)
        body = await request.body()
        values = body.decode("utf-8").replace('tweet_id=', '').split(',')
        if values == [""]:
            pass
        elif len(values) < 17:
            delete_failed_flag = False
            for v in values:
                try:
                    twitter_client = client
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


    except Exception as e:
        print(e)
        return templates.TemplateResponse('error.html', {"request": request})


if __name__ == '__main__':
    if os.environ['MODE'] == 'dev':
        uvicorn.run(app, port=4242, host='0.0.0.0')
