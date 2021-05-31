__author__ == "houcheng"

import datetime
import time

# https://github.com/kotartemiy/pygooglenews
from pygooglenews import GoogleNews

# https://github.com/codelucas/newspaper
from newspaper import Article

class GoogleNewsExtractor:
    
    def __init__(self, handle, id_filter, lang = 'en', country = 'US'):
        self.TIME_FORMAT = '%Y-%m-%d'
        self.nan = ''
        
        self.__goog_news = GoogleNews(lang, country)
        self.__handle = handle
        self.__id_filter = id_filter
        
    def __extract_entry(self, entry):
        """https://pythonhosted.org/feedparser/reference.html"""
        tmp_url = entry['link']
        
        try:
            tmp_id = entry['id']
            if not self.__id_filter(tmp_id):
                return
        except Exception:
            tmp_id = self.nan
            
        try:
            tmp_publish_ts = time.mktime(entry['published_parsed'])
        except Exception:
            tmp_publish_ts = self.nan
        
        try:
            tmp_title = entry['title']
        except Exception:
            tmp_title = self.nan
            
        try:
            tmp_source = 'NEWS: ' + entry['source']['title']
        except Exception:
            tmp_source = 'NEWS'
            
        try:
            article = Article(tmp_url)
            article.download()
            article.parse()
            if article.meta_description:
                tmp_abstract = article.meta_description
            elif article.text:
                tmp_abstract = article.text
            else:
                tmp_abstract = self.nan
        except Exception:
            tmp_abstract = self.nan
        
        # TODO: Perform NLP to understand if this is an incident and extract its time and location
        tmp_location = self.nan
        tmp_ts = self.nan
            
        self.__handle([tmp_id, tmp_ts, tmp_publish_ts, tmp_title, tmp_abstract, tmp_location, tmp_url, tmp_source])
        
    def search_and_extract(self, query, time_end, time_delta):
        end = time_end.strftime(self.TIME_FORMAT)
        start = (time_end - time_delta).strftime(self.TIME_FORMAT)

        response = self.__goog_news.search(query, from_=start, to_=end)
        for entry in response['entries']:
            self.__extract_entry(entry)