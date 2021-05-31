#!/usr/local/bin/python3.9
# -*- coding: utf-8 -*-
__author__ = 'Jason'
import tweepy

# Authenticate to Twitter
auth = tweepy.OAuthHandler("pGBDoAaEpkliVKBOLwjtcmHGc",
    "xF3g1wrP50b6BlZEd20u4oVfjgH1FGQcuWUzlQO5aUWOufvlhw")
auth.set_access_token("622518493-6VcLIPprbQbv9wkcBBPvCle8vsjU9fE85Dq9oStl",
    "tH9aKQbQQ1iRdYTcLSsPwitl44BkAc6jilrsU0ifnXvZhq")

api = tweepy.API(auth)

class StreamListener(tweepy.StreamListener):
    def on_data(self, data):
        print(data)
        return(True)
    def on_status(self, status):
        print(status.text)
    def on_error(self, status_code):
            if status_code == 420:
                return False

try:
    api.verify_credentials()
    print("Authentication OK")
    Listener = StreamListener()
    myStream = tweepy.Stream(auth = auth, listener=Listener)
    # stream works with single user. need multiple threads needs
    myStream.filter(follow=["17393196"])
except:
    print("Error during authentication")