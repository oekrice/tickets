#Test for basic functions
from obtain_data import find_basic_info

origin = "YRK"; destination = "NCL"
request_info = {"origin": origin, "destination": destination}   #Can add time constraints to this later
find_basic_info(request_info)
