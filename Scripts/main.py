import pytwitter
from pytwitter import Api
import getpass
import pandas as pd
import re
import json
import flask
import os
from flask import Flask, render_template_string, redirect, request

# Load Webpage strings
homePage = '''
<!doctype html>
<html>
    <head>
        <!-- Bootstrap CSS --> 
        <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0/css/bootstrap.min.css" integrity="sha384-Gn5384xqQ1aoWXA+058RXPxPg6fy4IWvTNh0E263XmFcJlSAwiGgFAW/dAiS6JXm" crossorigin="anonymous">
    </head>
    <body>
        <div class="container" style="padding:10px">
                <div class="card mb-3 h-100">
                    <div class="card-header">Welcome to socAIl! Please Enter your User ID Below </div>     
                    <div class="card-body"> 
                        <form method="POST" action="setUser"> 
                            <div class="form-group" role="group" > 
                                <label for="setUser">Please Enter Your User ID Here</label>
                                <input type="text" class="form-control" id="setUser" placeholder="@ESPN" name=user>
                            </div>
                                <button type="submit" class="btn btn-primary">Submit</button>
                            </div>
                        </form> 
                    </div>    
                </div>
        </div>
    </body>
</html>    '''
returnPage = '''
<!doctype html>
<html>
   <body>
     <strong>{} Profane Tweets Found</strong>
   </body>
</html>
'''

def loadWords():
    f = open("../Docs/profane_words.json", 'r')
    bad_words = json.load(f)
    return bad_words


def initTwitter():
    bearer_token = os.environ['BEARER_TOKEN']
    api = Api(bearer_token)
    return api


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
    return flag_count, flags_found


def flagDFProces(df):
    df['flags'] = df['text'].apply(lambda x: flag_check(bad_words, x))
    df['occurance'] = df['flags'].apply(lambda x: 1 if x[0] > 0 else 0)
    return df

#  Per request
def main(user_id):
    df = scrape_tl(user_id, 100)
    print(f"Timeline Scrape Complete {df.shape[0]} tweet's collected")
    processed_df = flagDFProces(df)
    profane_df = processed_df[processed_df.occurance == 1]
    print(f"{profane_df.shape[0]} Profane Tweets Found")
    return profane_df

def initWebsite(homePage, returnPage):
    app = Flask(__name__)

    @app.route("/", methods=['GET'])
    def home():
        return render_template_string(homePage)

    @app.route("/setUser", methods=["POST"])
    def setUser():
        user = request.form["user"]
        p_count = str(main(user).shape[0])
        return render_template_string(returnPage.replace('{}', p_count))

    app.run(debug=False)


#  initialization
bad_words = loadWords()
api = initTwitter()
initWebsite(homePage,returnPage)
print("Initialization Complete http://127.0.0.1:5000/ ")





#out = main(3241550339)
