#!/usr/local/bin/python3.9
# -*- coding: utf-8 -*-
__author__ = 'Jason'

import twint
import psycopg2

tablename = 'twitter'

def check_table_exists(tablename):
    conn = psycopg2.connect(database='jason', user="jason", password="", host="127.0.0.1")
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = '{0}'
        """.format(tablename.replace('\'', '\'\'')))
    if cur.fetchone()[0] == 1:
        cur.close()
        return True

    cur.close()
    return False

def create_table(tablename):
    conn = psycopg2.connect(database='jason', user="jason", password="", host="127.0.0.1")
    cur = conn.cursor()
    if not check_table_exists(conn, tablename):
        try:
            cur.execute("""DROP TABLE IF EXISTS '{0}'""".format(tablename.replace('\'', '\'\'')))
            cur.execute('''
            CREATE TABLE '{0}' (
                ID  SERIAL PRIMARY KEY,
                timestamp TEXT,
                user_id TEXT,
                username text,
                name text,
                tweet text,
                mentions text,
                urls text,
                hashtags TEXT,
                cashtags TEXT,
                link text,
                geo text,
                source text);
            '''.format(tablename.replace('\'', '\'\'')))
            conn.commit()
            conn.close()
            print("Table created successfully")
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)

def insert_data(data):
    conn = psycopg2.connect(database='jason', user="jason", password="", host="127.0.0.1")
    sql = "INSERT INTO twitter(timestamp, user_id, username, name, tweet, mentions, urls, hashtags, cashtags, link, geo, source) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    try:
        cur = conn.cursor()
        cur.execute(sql, data)
        conn.commit()
        conn.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)


# Police departmetn twitter ids
twitter_ids = [
'DCPoliceDept',
'NYPDnews',
'RochesterNYPD',
'Austin_Police',
'MiamiPD',
'LAPDHQ',
'LAPDWestLA',
'LAPDHollywood',
'PomonaPD',
'MontereyParkPD',
'covinapd',
'WestCovinaPD',
'Visaliapd',
'FremontPD',
'SanBernardinoPD',
'Chicago_Police',
'MinneapolisPD',
'SeattlePD',
'boulderpolice',
'SanDiegoPD',
'Atlanta_Police',
'PaloAltoPolice',
'DallasPD',
'houstonpolice',
'DaytonPolice',
'CSPDPIO',
'ColumbiaPDSC',
'PhoenixPolice',
'FranklinTNPD',
'TulsaPolice',
'bostonpolice',
'SLMPD',
'PortlandPolice',
'PPBPIO',
'WestwoodPD'
]

# TODO: fecth all hashtags on twitter
hashtags = [
    '#blacklivesmatter',
    '#stopasianhate',
    '#StopAAPIHate',
]

# TODO: Filter by following keywords
keywords = [
    'WANTED for CRIMINAL MISCHIEF',
]

# Fetch infomration
for twitter_id in twitter_ids:
    c = twint.Config()
    c.Username = twitter_id
    # fetch all tweets of each account if following line is being removed.
    c.Limit = 1
    c.Store_object = True
    c.Hide_output = True
    twint.run.Search(c)

    tweets = twint.output.tweets_list
    for tweet in tweets:
        data = (
            tweet.timestamp, tweet.user_id, tweet.username, tweet.name, tweet.tweet, tweet.mentions, tweet.urls, tweet.hashtags, tweet.cashtags, tweet.link, tweet.geo, tweet.source
        )
        try:
            insert_data(data)
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)