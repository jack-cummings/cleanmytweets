import tweepy
import pandas as pd
import re
import json
import os
import datetime
from pandas import ExcelWriter

def loadWords():
    f= open("references/profane_words.json", 'r')
    bad_words = json.load(f)
    bad_words_pattern = ' | '.join(bad_words)
    return bad_words_pattern, bad_words

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
    print(f"{name}'s timeline extract complete. {timeline_df.shape[0]} Tweets")
    return timeline_df

def flagDFProces(df):
    df['Profane Words'] = df['Tweet'].apply(lambda x: ','.join(re.findall(bad_words_pattern, x)))
    df['occurance'] = df['Profane Words'].apply(lambda x: 1 if len(x) > 0 else 0)
    df['Date'] = df['date_full'].apply(lambda x: datetime.datetime.date(x))
    out_df = df[df['occurance']==1]
    out_df = out_df[['Tweet','Profane Words', 'Date']]
    return out_df

def main(users):
    out_dfs = {}
    for user in users:
        df = scrape_tl_username(user)
        out_df = flagDFProces(df)
        out_dfs.update({user:out_df})
    return out_dfs

def writeExcel(df_dict, outpath):
    with ExcelWriter(outpath) as writer:
        for user, df in df_dict.items():
            df.to_excel(writer, user)

users = ['@timothyjmckay','@Jada_Boyd55']
bad_words_pattern, bad_words = loadWords()
api = initTwitter()
dfs = main(users)
writeExcel(dfs,'exp/user_report.xlsx')





