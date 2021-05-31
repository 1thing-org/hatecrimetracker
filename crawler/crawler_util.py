import csv
import datetime
from crawler.pygooglenews_util import GoogleNewsExtractor

class NewsCrawler:
    
    def __init__(self, name, query, path = ''):
        self.OUTFILE_FORMAT = '{path}{name}_{date}.csv'
        self.TIME_DELTA = datetime.timedelta(1)

        self.time_format = '%Y-%m-%d'        
        self.name = name
        self.query = query
        self.path = path
        
        self.__id_set = set()
        
    def __filte_by_id(self, id_str):
        """
        Return False iff |id_str| is duplicate. Otherwise return True and add it into the set.
        """
        if id_str in self.__id_set:
            return False
        else:
            self.__id_set.add(id_str)
            return True
        
    def __get_filename(self, date):
        return self.OUTFILE_FORMAT.format(path=self.path, name=self.name, date=date.strftime(self.time_format))
    
    def __write_csv_header(self, csv_file):
        csv_file.writerow(['id', 
                           'incident_time',
                           'created_on', 
                           'title', 
                           'abstract', 
                           'incident_location', 
                           'url', 
                           'incident_source'])
    
    def __make_one_csv(self, outfile_name, time_end):
        with open(outfile_name, 'w') as outfile:
            f = csv.writer(outfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            self.__write_csv_header(f)
            
            gne = GoogleNewsExtractor(f.writerow, self.__filte_by_id)
            gne.search_and_extract(self.query, time_end, self.TIME_DELTA)
        
    def update_id_set_from_files(self, infile_names):
        for infile_name in infile_names:
            with open(infile_name, 'r') as infile:
                f = csv.reader(infile, delimiter=',', quotechar='"')
                # skip header
                row = next(f)
                if row[0] != 'id':
                    self.__id_set.add(row[0])
                
                for row in f:
                    self.__id_set.add(row[0])    
        
    def make_csv_for_yesterday(self):
        outfile_name = self.__get_filename(datetime.datetime.now() - self.TIME_DELTA)
        
        self.__make_one_csv(outfile_name, datetime.datetime.now())
        
    def make_csv(self, time_end, num_days):
        curr = time_end
        for i in range(num_days):
            outfile_name = self.__get_filename(curr - self.TIME_DELTA)
            self.__make_one_csv(outfile_name, curr)
            
            curr -= self.TIME_DELTA