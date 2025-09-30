def rank_stations(request_info, station_info):
    #This is for determining which stations it is worthwhile having a look at. 
    #For now, pick the ones which are best for time, and the (potentially) best for price, without any kind of mingling of the two concepts
    times = []; prices = []; stats= []
    print(station_info)
    for station in station_info:
        #Sort the stations based on the above
        prices.append(station_info[station]["price_score"])
        times.append(station_info[station]["time_score"])
        stats.append(station)
        #print(station)
    timelist = list(zip(times, stats))
    timelist.sort(key=lambda x: x[0])
    _, sort_times = zip(*timelist)
    pricelist = list(zip(prices, stats))
    pricelist.sort(key=lambda x: x[0])
    _, sort_times = zip(*pricelist)

    print(timelist[:20])
    print(pricelist[:20])
    return