
from crawler.crawler_util import NewsCrawler

PROJECT_NAME = 'asian_hate_crime'
QUERY = '"asian hate crime" AND ("report" OR "incident")'

def make_csv_from_google_news_for_yesterday():
    news_crawler = NewsCrawler(name=PROJECT_NAME, query=QUERY)
    news_crawler.make_csv_for_yesterday()
    
def make_csv_from_google_news_for_range(time_end, num_days):
    news_crawler = NewsCrawler(name=PROJECT_NAME, query=QUERY)
    news_crawler.make_csv(time_end, num_days)
