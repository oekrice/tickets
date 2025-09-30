#Test for basic functions
from obtain_data import find_basic_info, find_station_info
from datetime import datetime as dt, timedelta
import datetime
import geopy.distance

origin = "NCL"; destination = "KGX"
request_info = {"origin": origin, 
                "destination": destination, 
                "start_time": datetime.time(12,00), 
                "date": dt.today() + timedelta(days = 1), 
                "end_time": datetime.time(15,00),
                }   

station_info = find_station_info(request_info)   #This will attempt to rank the stations in the request based on geography, THEN other things like timing and price (which will take a request).
#basic_journeys = find_basic_info(request_info)
