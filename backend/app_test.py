#Test for basic functions
from obtain_data import find_basic_info, find_station_info
from data_functions import rank_stations
from datetime import datetime as dt, timedelta
import datetime
import geopy.distance

origin = "YRK"; destination = "KET"
request_info = {"origin": origin, 
                "destination": destination, 
                "start_time": datetime.time(12,00), 
                "date": dt.today() + timedelta(days = 1), 
                "end_time": datetime.time(15,00),
                "ignore_previous": False
                }   

station_info = find_station_info(request_info)   #This will attempt to rank the stations in the request based on geography, THEN other things like timing and price (which will take a request).
station_checks = rank_stations(request_info, station_info)

#basic_journeys = find_basic_info(request_info)
