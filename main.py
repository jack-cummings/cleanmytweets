import tweepy
import pandas as pd
import re
import json
import os
import datetime
import stripe
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse

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
        basepath = 'http://0.0.0.0:8000'
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


@app.get("/")
async def home(request: Request):
    authorization_url = app.auth.get_authorization_url()
    return templates.TemplateResponse('index_j.html', {"request": request, "user_auth_link": authorization_url})


@app.route('/return')
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


# Fetch the Checkout Session to display the JSON result on the success page
@app.get('/checkout-session', response_model=stripe.checkout.Session)
def get_checkout_session(
        sessionId: str
):
    id = sessionId
    checkout_session = stripe.checkout.Session.retrieve(id)
    return checkout_session


@app.post('/create-checkout-session')
def create_checkout_session():
    domain_url = os.getenv('DOMAIN')
    try:
        # Create new Checkout Session for the order
        # Other optional params include:

        # For full details see https:#stripe.com/docs/api/checkout/sessions/create
        # ?session_id={CHECKOUT_SESSION_ID} means the redirect will have the session ID set as a query param
        checkout_session = stripe.checkout.Session.create(
            success_url=domain_url + '/static/success.html?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=domain_url + '/static/canceled.html',
            payment_method_types=(os.getenv('PAYMENT_METHOD_TYPES') or 'card').split(','),
            mode='payment',
            line_items=[{
                'price': os.getenv('PRICE'),
                'quantity': 1,
            }]
        )
        return RedirectResponse(
            checkout_session.url,
            status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        raise HTTPException(403, str(e))

    return RedirectResponse(checkout_session.url, code=303)


@app.route("/scan_tweets")
async def scan_tweets(request: Request):
    # Get Tweets
    tweets_out = []
    for tweet in tweepy.Paginator(app.client.get_users_tweets, id=app.user_id,
                                  tweet_fields=['id', 'text', 'created_at'], max_results=100).flatten(limit=500):
        tweets_out.append([tweet.id, tweet.text, tweet.created_at])

    timeline_df = pd.DataFrame(tweets_out, columns=['Delete?', 'Text', 'date_full'])
    df = timeline_df

    total_count = df.shape[0]
    out_df = flagDFProces(df)
    prof_df = out_df[out_df['occurance'] == 1]

    check_box = r"""<input type="checkbox" id="\1" name="tweet_id" value="\1">
                            <label for="\1">  </label><br>"""
    out_table_html = str(re.sub(r'(\d{18,19})', check_box,
                                prof_df.drop(['date_full', 'occurance'], 1).to_html(index=False).replace('<td>',
                                                                                                         '<td align="center">')))
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
        uvicorn.run(app, port=8000, host='0.0.0.0')
