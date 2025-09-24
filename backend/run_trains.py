# -*- coding: utf-8 -*-
"""
Created on Sun Dec 25 13:10:17 2022

@author: eleph
"""

import csv
import numpy as np
import time
import geopy.distance
import threading
import matplotlib.pyplot as plt
from lxml import html
import requests
import os
import cartopy.crs as ccrs
import cartopy.feature as cfeature

'''
This version aims to do a QUICK search of all the possible stations, and then an in-depth search of the best 50 or so. 
Probably worthwhile for longer journeys maybe perhaps
'''

class parameters:
    '''
    Class for all the parameters that need to stay constant throughout. Saves passing them around the whole time.
    Also variables that are shared between everywhere
    '''
    def __init__(self, start_station, end_station, day, start_time, end_time, quick = False, t_extra = 65, ignore_log = False, redo = False, redo2 = False):
        self.start_station = start_station
        self.end_station = end_station
        self.day = day
        self.start_time = start_time
        self.end_time = end_time
        self.t_extra = t_extra
        self.quick = quick
        self.p_extra = 0.0   #extra cost allowed from the minimum (pounds)
        self.matrix_res = 15.  #time interval at which you don't care which train you catch (eg. within 15 minutes)
        if quick:
            self.check_max = 50   #Maximum stations checked in the initial split
            self.d_fact = 1.6
        else:
            self.check_max = 250
            self.d_fact = 1.6  #max extra distance travelled on the journey

        self.ignore_log = ignore_log  #If the search has happened before (with a decent time frame), setting this to False can speed things up. But be careful.
        self.redo = redo
        self.redo2 = redo2
        self.plotinfo = []
        self.time_start = time.time()


class station_info:
    '''
    Loads and imports station information from the csv file with coordinates. All alphabetical but hasn't been checked for errors yet
    '''
    def __init__(self):
        statlist = csv.reader(open('station_coordinates.csv'))
        self.list = []
        for stat in statlist:
            self.list.append(stat)
        self.list = np.array(self.list)
        
    def totime(self, string):
        h = string.strip()[:2]
        m = string.strip()[3:5]
        return float(h)*100 + float(m)
    
    def timestring(self, time):
        time = float(time)
        if time < 1000:
            return '0' + str(time)[:3]
        else:
            return str(time)[:4]
        
    def daystring(self, day):
        tstring = str(day)
        if len(tstring) == 5:
            return '0' + tstring
        else:
            return tstring[:6]
    
    def distance(self, code1, code2):  
        ind1 = np.where(self.list[:,0] == code1)[0]
        ind2 = np.where(self.list[:,0] == code2)[0]
        c1 = [self.list[ind1,2], self.list[ind1,3]]
        c2 = [self.list[ind2,2], self.list[ind2,3]]
        try:
            return geopy.distance.geodesic(c1, c2).miles
        except:
            return -1.
        
    def makeurl_nr(self, start, end, d, t):
        s1 = "https://ojp.nationalrail.co.uk/service/timesandfares/"
        s2 = "/"
        s3 = "dep"
        return s1 + start + s2 + end + s2 + self.daystring(d) + s2 + self.timestring(t) + s2 + s3
  
    def toprice(self, string):
        return float(string.strip()[1:])
    
    def alldists(self, code):
        '''
        Runs through all stations and provides distances. Should be worthwhile most of the time
        '''
        dists = []
        ind1 = np.where(self.list[:,0] == code)[0]
        c1 = [self.list[ind1,2], self.list[ind1,3]]
        for i in range(len(self.list)):
            dists.append(geopy.distance.geodesic([self.list[i][2], self.list[i][3]], c1).miles)
        return np.array(dists)

def find_journey_info(stats, start_station, end_station, day, start_time, end_time = -1.,page_limit=False):
    '''
    Finds the departure and arrival times between the two stations plus price and changes.
    Trains must arrive before end_time but this will not include every possible iteration,
    just those on the national rail website.
    Ouputs as a list, each entry is depart, arrive and price
    '''
    journeys = []   #to be appended to
    go = True
    pagecount = 0
    page_start = stats.timestring(start_time)
    while go:   #cycling through pages
        if start_station == end_station:
            return []
        url = stats.makeurl_nr(start_station, end_station, day, stats.timestring(page_start))
        try:
            page = requests.get(url)
            tree = html.fromstring(page.content)
        except:
            print('Internet error, probably. Waiting and trying again...')
            journeys = []   #to be appended to
            go = True
            pagecount = 0
            page_start = stats.timestring(start_time)
            time.sleep(10.0)
            continue 
        if str(page) == "<Response [403]>":
            #print('National rail have cottoned on. Waiting a bit and trying again...')
            journeys = []   #to be appended to
            go = True
            pagecount = 0
            page_start = stats.timestring(start_time)
            time.sleep(60.0)
            continue
        
        dep = tree.xpath('//div[@class="dep"]/text()')
        arr = tree.xpath('//div[@class="arr"]/text()')
        price = tree.xpath('//label[@class="opsingle"]/text()')    
        if page == '<Response [200]>':
            return []
        if len(dep) > 0 and len(price) == len(dep)*2:
            for i in range(len(dep)):
                dep1 = stats.totime(dep[i])
                #print(dep1)
                arr1 = stats.totime(arr[i])
                #Sometimes no fares are available for strange reasons (metros and things)
                if len(price[i*2+1].strip()) == 0:
                    pass
                else: 
                    p1 = stats.toprice(price[i*2+1])
                    if dep1 >= float(page_start) and arr1 <= float(end_time) and arr1 > dep1 and arr1 > float(page_start):
                        journeys.append([float(dep1), float(arr1), float(p1)]) 
                if arr1 < float(page_start):
                    go = False
            if arr1 < float(end_time) and arr1 > float(page_start):
                pagecount += 1
                #print(pagecount, start_station, end_station, dep1, page_start)
                
                if int(dep1%100) == 59:
                    if dep1 + 41 <= float(page_start):
                        go = False
                    page_start = dep1+41  
                else:
                    if dep1 + 1 <= float(page_start):
                        go = False
                    page_start = dep1 + 1
            else:
                go = False
        else:
            go = False
        if pagecount > 25:
            return []
        if page_limit:
            go = False
            
    return journeys

def timediff(t1, t2):
    #Difference in minutes between two times. Time is horrid to deal with
    dt = float(t2 - t1)
    if t2%100 < t1%100:
        dt = dt-40   #this is tricksy because time. The hours should be fine
    dt = dt%100 + 60*(dt//100)
    return float(dt)


def create_price_matrix(start, end, matrix_res):
    '''
    Creates a blank price matrix, for further splits to be compared against. 
    The resolution is the number of minutes between each block (try to keep to 15, 60 etc.)
    '''
    ncells = int(60*24/matrix_res + 1)
    
    
    return np.inf*np.ones((ncells, ncells))
    
def update_matrix(matrix, completes):
    ncells = len(matrix[0])
    dt_all = 60*24
    for complete in completes:
        j_start = complete[0][2]
        j_end = complete[-1][1]
        t0 = timediff(0, j_start)
        t1 = timediff(0, j_end)
        cell1 = int(ncells*(t0-1)/dt_all) 
        cell2 = int(ncells*(t1)/dt_all) 
        p1 = sum(np.array(complete)[:,3].astype(float))   #price point. Need to test this later.
        matrix[:cell1+1, cell2:] = np.minimum(p1, matrix[:cell1+1, cell2:])
        
    return matrix

def plotmat(matrix, start_time, end_time, completes = []):
        
    fig = plt.figure(figsize = (10,7))
    ncells = len(matrix[0])
    
    xs = np.linspace(0,60*24,ncells+1)
    
    plot_matrix = matrix.copy()
    plot_matrix[plot_matrix > 1e6] = 0.0

    if len(paras.plotinfo) == 0:
        vmin = 0.0#max(np.min(matrix)/2.0, 0.0)
        vmax = np.max(plot_matrix)
    else:
        vmin = paras.plotinfo[0][0]
        vmax = paras.plotinfo[0][1]
        
    print(vmin, vmax)
    
    plt.pcolormesh(xs,xs,plot_matrix.T,vmin = vmin, vmax = vmax,cmap = 'plasma')
    plt.colorbar(label='Price')
    
    minx = 60*24; maxx = 0
    miny = 60*24; maxy = 0
    
    minp = 1e6
    
    
    
    for journey in completes:
        x = timediff(0.0,journey[0][2]); y = timediff(0.0,journey[-1][1])
        minx = min(x, minx); maxx = max(x, maxx)
        miny = min(y, miny); maxy = max(y, maxy)
        minp = min(minp, sum(np.array(journey)[:,3].astype(float))) 

        if len(journey) == 2:  #not a split
            plt.scatter(x,y, c = 'red', edgecolor = 'black')
        elif len(journey) == 3:
            plt.scatter(x,y, c = 'yellow', edgecolor = 'black')
        elif len(journey) == 4:
            plt.scatter(x,y, c = 'green', edgecolor = 'black')
        else:
            plt.scatter(x,y, c = 'orange', edgecolor = 'black')

    plt.gca().set_xticks(np.linspace(0,1440,25))
    plt.gca().set_yticks(np.linspace(0,1440,25))
    plt.xlabel('Depart After')
    plt.ylabel('Arrive Before')
    plt.title('Minimum (no railcard) price £%.2f' % minp)
    tlabels = []
    for i in range(25):
        tlabels.append('%d:00' % i)
        
    plt.gca().set_xticklabels(tlabels, rotation='vertical')
    plt.gca().set_yticklabels(tlabels, rotation='horizontal')
    
    
    if len(paras.plotinfo) == 0:
        plt.xlim(minx-30, maxx+30)
        plt.ylim(miny-30, maxy+30)
        paras.plotinfo.append([vmin,vmax])
        paras.plotinfo.append([minx-30, maxx+30])
        paras.plotinfo.append([miny-30, maxy+30])
        
    else:
        plt.xlim(paras.plotinfo[1])
        plt.ylim(paras.plotinfo[2])

    if paras.plot_count == 0:
        plt.savefig('prices_unsplit.png')
    else:
        plt.savefig('prices_split.png')

    plt.show()
    
    
    
def minppm(paras, stats, completes):
    #Returns minimum price per mile of the existing journeys
    p = 1e6
    for check in completes:
        dist = stats.distance(check[0][0], check[-1][0])
        p1 = sum(np.array(check)[:,3].astype(float)) 
        if p1/dist < p:
            p = p1/dist    
    return p

def printnice(journeys):
    '''
    Function to print journeys nicely
    '''
    for split in journeys:
        p1 = sum(np.array(split)[:,3].astype(float))
        print('')
        print('Price: £',  "{:.2f}".format(p1), ', Time:', "{}".format(int(timediff(float(split[0][2]), float(split[-1][1])))), 'minutes:')
        print('--------------------------------------------------')
        for k in range(len(split)-1):
            print('Depart', split[k][0], 'at', int(split[k][2]), ', arrive', split[k+1][0], 'at', int(split[k+1][1]), '. Ticket cost £ ', "{:.2f}".format(split[k+1][3]))
        print('--------------------------------------------------')
        
def savenice(journeys):
    '''
    Function to print journeys nicely
    '''
    fname = 'output' + paras.start_station + paras.end_station + '.txt'
    if os.path.exists(fname):
        os.remove(fname)
    with open(fname, "a") as myfile:
        for split in journeys:
            p1 = sum(np.array(split)[:,3].astype(float))
            myfile.write('' + "\n")
            myfile.write('Price: £' + str(p1) + ', Time:' + str(int(timediff(float(split[0][2]), float(split[-1][1])))) + ' minutes:' + "\n")
            myfile.write('--------------------------------------------------' + "\n")

            for k in range(len(split)-1):
                myfile.write('Depart ' +  split[k][0] + ' at ' + str(split[k][2]) + ', arrive ' + split[k+1][0] + ' at ' + str(split[k+1][1]) + '. Ticket cost £ ' +  str(split[k+1][3]) + "\n")
            myfile.write('--------------------------------------------------' + "\n")
            
            myfile.write('' + "\n")


def find_geog_splits(stats, distance_factor):
     #Finds the geogrphically reasonable split stations, for the first split only.
     #Should speed things up considerably for short journeys
     init_stats = []
     for check in stats.list:
         add = True
         dnew = stats.distance(paras.start_station, check[0]) + stats.distance(check[0], paras.end_station)
         dold = stats.distance(paras.start_station, paras.end_station)
         if dnew/dold > distance_factor:
             add = False    
         if check[0] == paras.start_station or check[0] == paras.end_station:
             add = False
         if add == True:  #Satisfies geographical criterion
             init_stats.append(check[0])
     return init_stats
          
def complete_init_splits(paras, stats, init_stats):
    
    '''
    Latest update here to do different things if the journey has been done and saved out
    If this is NOT the case then the init splits need to be done quickly - only one request per station, then saved out and tried again
    '''
    # This runs through the possible split stations, determines whether they are feasible and then filters after updating the matrix
    # Also needs functionality to save out info for the stations tested so it is faster to do this stage in future (have a limiter on out-of-wayness)
    paras.raw_completes = []
    paras.filtered_completes = []#paras.inits.copy()
    
    def single_split(paras, stats, stat_check):
        #For use in the threading thing. Only two checks per thread, which is nice. 
        mtime = 1e6
        journeys_1 = find_journey_info(stats, paras.start_station, stat_check, paras.day, paras.start_time, paras.end_time)

        if len(journeys_1) > 0:
            journeys_2 = find_journey_info(stats, stat_check, paras.end_station, paras.day, journeys_1[0][1], paras.end_time)
            if len(journeys_1) > 0 and len(journeys_2) > 0:   #This is possible time-wise
                for i, j2 in enumerate(journeys_2):
                    for j, j1 in enumerate(journeys_1):
                        if j2[0] > j1[1]:  #works time-wise
                            complete = [[paras.start_station, paras.start_time, j1[0],0.],[stat_check, j1[1], j2[0],j1[2]],[paras.end_station, j2[1], paras.end_time,j2[2]] ]
                            mtime = min(mtime, timediff(j1[0], j2[1]))
                            if timediff(j1[0], j2[1]) <= paras.base_tmax + paras.t_extra:
                                paras.raw_completes.append(complete)     

        
    def generate_log(paras, stats, stat_check):
        #Generates the station log, if this is the first time without an existing log
        mtime = 1e6
        journeys_1 = find_journey_info(stats, paras.start_station, stat_check, paras.day, 400, 2359,page_limit=True)
        d0 = stats.distance(paras.start_station, stat_check)
        d1 = stats.distance(stat_check, paras.end_station)
        if len(journeys_1) > 0:
            journeys_2 = find_journey_info(stats, stat_check, paras.end_station, paras.day, journeys_1[0][1], 2359,page_limit=True)
            if len(journeys_1) > 0 and len(journeys_2) > 0:   #This is possible time-wise
                for i, j2 in enumerate(journeys_2):
                    for j, j1 in enumerate(journeys_1):
                        if j2[0] > j1[1]:  #works time-wise
                            complete = [[paras.start_station, paras.start_time, j1[0],0.],[stat_check, j1[1], j2[0],j1[2]],[paras.end_station, j2[1], paras.end_time,j2[2]] ]
                            mtime = min(mtime, timediff(j1[0], j2[1]))
                            if timediff(j1[0], j2[1]) <= paras.base_tmax + paras.t_extra:
                                paras.raw_completes.append(complete)     
                paras.stat_log.append([stat_check,mtime,d0,d1])    

        
        
    if not paras.log_exists:
        #Need to establish doable stations as quickly as possible here, then save the log. 
        #If not, no need to save out a log. 
        #Should be more thorough than the original way of doing it
        paras.stat_log = []
        print('Running without log - creating log now')
        print('Searching', len(init_stats), 'stations that meet geographical constraints')
        nthreads = 250#len(init_stats)   #Nice to see the progress here
        nbases = len(init_stats[:])
        nchunks = int(nbases/nthreads) + 1
        threads = []
        for chunk in range(nchunks):
            for j in range(nthreads*chunk, min(nbases, nthreads*(chunk+1))):
                stat_check = init_stats[j]
                x = threading.Thread(target=generate_log, args=(paras, stats, stat_check), daemon = False)
                threads.append(x)
                x.start()
            for j, x in enumerate(threads):
                x.join()
            print('%.1f %% done' % min(100,(100*(chunk+1)*nthreads/nbases)))       
    
        #Sort the station log here
        stat_inds = np.array(np.array(paras.stat_log)[:,1].astype('float').argsort())
        paras.stat_log = np.array(paras.stat_log)[stat_inds]
        #Save out stat_log (if larger than existing file)
        np.save(paras.log_fname, paras.stat_log,allow_pickle=True)
        print('Intermediate Station Log Saved with', len(paras.stat_log), 'stations. This step will not need to be done again for the same journey.')
        
    else:
        print('Searching best', len(init_stats), 'stations that meet time constraints')
        nthreads = 50#len(init_stats)   #Nice to see the progress here
        nbases = len(init_stats[:])
        nchunks = int(nbases/nthreads) + 1
        threads = []
        for chunk in range(nchunks):
            for j in range(nthreads*chunk, min(nbases, nthreads*(chunk+1))):
                stat_check = init_stats[j]
                x = threading.Thread(target=single_split, args=(paras, stats, stat_check), daemon = False)
                threads.append(x)
                x.start()
            for j, x in enumerate(threads):
                x.join()
            print('%.1f %% done' % min(100,(100*(chunk+1)*nthreads/nbases)))     
            
            
    print(len(paras.raw_completes), 'splits found')
        
    paras.complete1s = np.array(paras.inits + paras.raw_completes, dtype = 'object')
    
    np.save(paras.split_fname1, paras.complete1s, allow_pickle = True)

def plotmap(paras,stats):
    '''
    PLots a map of stations (based on out-of-wayness?) with perhaps the journeys between them
    '''
    fig = plt.figure(figsize = (15,10))
    ax = plt.axes(projection=ccrs.Mollweide())
    
    ax.add_feature(cfeature.LAND)
    ax.add_feature(cfeature.BORDERS)
    ax.add_feature(cfeature.COASTLINE)
    ax.add_feature(cfeature.OCEAN)
    ######################################
    #Adding splits as lines
    print('Plotting map')
    writelist = []
    if True:
        #Plot cheapest journey options here. 
        for i in range(len(paras.filtered_completes)):
            journey = paras.filtered_completes[i]
            for j in range(len(journey)-1):
                stat1 = journey[j][0]; stat2 = journey[j+1][0]
                ind1 = np.where(stats.list[:,0] == stat1)[0]
                ind2 = np.where(stats.list[:,0] == stat2)[0]
                c1 = [float(stats.list[ind1,2][0]), float(stats.list[ind1,3][0])]
                c2 = [float(stats.list[ind2,2][0]), float(stats.list[ind2,3][0])]
                ppm = journey[j+1][-1]/geopy.distance.geodesic(c1,c2).miles
                plt.plot([c1[1], c2[1]],[c1[0],c2[0]], transform=ccrs.Geodetic(), c = 'black',zorder = 0)
                writelist.append(stat2)
    ###################################
    #ADDING STATIONS AS DOTS
    maxlon = -180; minlon = 180
    maxlat = -90; minlat = 90
    paras.stat_log = np.array(paras.stat_log)

    minlog = np.min(np.array(paras.stat_log)[:,1].astype(float))
    paras.stat_log = np.array(paras.stat_log)
    for stat in paras.stat_log:
        size = 10./(float(stat[1]) - minlog + 1)**0.75
        ind1 = np.where(stats.list[:,0] == stat[0])[0]
        c1 = [float(stats.list[ind1,2][0]), float(stats.list[ind1,3][0])]
        minlon = min(minlon, c1[1]); maxlon = max(maxlon, c1[1])
        minlat = min(minlat, c1[0]); maxlat = max(maxlat, c1[0])
        plt.scatter(c1[1], c1[0], transform=ccrs.Geodetic(), c = 'red', s = size, edgecolor = 'black')
        if stat[0] in writelist:
            plt.annotate(stat[0], [c1[1]+0.02,c1[0]], transform=ccrs.Geodetic(), c = 'red')


    for stat in [[paras.start_station, '0.0'],[paras.end_station, '0.0']]:
        size = 20.
        ind1 = np.where(stats.list[:,0] == stat[0])[0]
        c1 = [float(stats.list[ind1,2][0]), float(stats.list[ind1,3][0])]
        minlon = min(minlon, c1[1]); maxlon = max(maxlon, c1[1])
        minlat = min(minlat, c1[0]); maxlat = max(maxlat, c1[0])
        plt.scatter(c1[1], c1[0], transform=ccrs.Geodetic(), c = 'green', s = size, edgecolor = 'black')
        plt.annotate(stat[0], [c1[1]+0.02,c1[0]], transform=ccrs.Geodetic(), c = 'green')

    dlon = maxlon-minlon; dlat = maxlat - minlat
    extent = [minlon-dlon*0.2, maxlon+dlon*0.2, minlat-dlat*0.2, maxlat+dlat*0.2]
    ax.set_extent(extent)

    plt.savefig('map.png', dpi = 500)
    plt.close()

def initial_split(paras):
    '''
    New running algorithm with a bit more sophistication (hopefully) than the old one
     
    PLAN:
    Determine reasonable intermediate stations geographicallly. Create a file with all of these, including minimum time from start station and deviation from ideal route.
    Dont' disregard any at this point
    Save this data out so it doesn't always have to be done
    
    Load in data if that isn't done
    Determine order 1 splits
    
    Do modified Dijkstra on selected stations (order n^2 hopefully). Three degrees of sophistication here. 
    
    Try to be fancy with the order 1 splits
    
    (Maybe) look for dodgy options - staying on the train too long etc.
    
    Conect to stats website to calculate delay repay?   
    '''
    timer_start = time.time()
    print('Finding split journeys between', paras.start_station, 'and', paras.end_station, 'on day', paras.day)
    print('Departing after', paras.start_time, ', arriving before', paras.end_time)
    print('')
    

    def find_init_splits(distance_factor):
        #Finds the geogrphically reasonable split stations, for the first split only.
        #Should speed things up considerably for short journeys
        init_splits = []
        for check in stats.list:
            add = True
            dnew = stats.distance(paras.start_station, check[0]) + stats.distance(check[0], paras.end_station)
            dold = stats.distance(paras.start_station, paras.end_station)
            if dnew/dold > distance_factor:
                add = False    
            if check[0] == paras.start_station or check[0] == paras.end_station:
                add = False
            if add == True:  #Satisfies geographical criterion
                init_splits.append(check[0])
        return init_splits
        
    paras.start_time = float(paras.start_time); paras.end_time = float(paras.end_time)
    
    paras.split_fname0 = 'splits/' + paras.start_station + paras.end_station + str(paras.day) + str(paras.start_time) + str(paras.end_time) + 'all0.npy'
    paras.split_fname1 = 'splits/' + paras.start_station + paras.end_station + str(paras.day) + str(paras.start_time) + str(paras.end_time) + 'all1.npy'
    paras.split_fname2 = 'splits/' + paras.start_station + paras.end_station + str(paras.day) + str(paras.start_time) + str(paras.end_time) + 'all2.npy'
    
    paras.log_fname = 'logs/' + paras.start_station + paras.end_station + '.npy'

    ncells = int(60*24/paras.matrix_res)

    paras.matrix = np.inf*np.ones((ncells, ncells))

    stats = station_info()
    done1 = False
    if os.path.exists(paras.split_fname1) and not paras.redo and os.path.exists(paras.log_fname):
        print('Loading Existing Splits')
        done1 = True
    #This is a class with all the station information
    #stations.list lists them all, with each index having the code, name and coordinates
    #Class also contatins functions for distance between stations, national rail url etc.

    if not done1:
        ###################################
        #STEP 1: Find suitable journeys between the start and end using national rail. Always needs doing unless splits exist
        overall_journeys = find_journey_info(stats, paras.start_station, paras.end_station, paras.day, paras.start_time, paras.end_time)
        if len(overall_journeys) < 1:
            print('No journeys found on national rail... This may be incorrect...')
            #raise Exception('No possible journeys found for these parameters. Exiting.')
            overall_journeys = [[paras.start_time, paras.end_time, stats.distance(paras.start_station, paras.end_station)*1.0]]
        # Put into the journey format used in the last iteration of the code
        paras.inits = []
        base_tmax = 0  #slowest unsplit journey
        for i, j_raw in enumerate(overall_journeys):
            journey = [[paras.start_station, paras.start_time, j_raw[0],0.],[paras.end_station, j_raw[1], paras.end_time,j_raw[2]]]
            base_tmax = max(base_tmax, int(timediff(j_raw[0], j_raw[1])))
            paras.inits.append(journey)
        paras.base_tmax = base_tmax
        
        print('Initial journeys found, time taken %.2f s' % (time.time() - timer_start))
        # Initial unsplit journeys have been determined. Create price matrix for this at this point - may need to with other stations later on
        # Price matrix will now work in minutes since midnight. Just silly to do it a different way I think.
        #This will create and update the price matrix based on the unsplit journeys
        paras.matrix = update_matrix(paras.matrix, paras.inits)

        print('Initial Price Matrix Found, time taken %.2f s' % (time.time() - timer_start))
    
        np.save(paras.split_fname0, paras.inits, allow_pickle = True)
        np.save('data/' + str(paras.start_station) + str(paras.end_station) + str(paras.day) + 'split0', paras.inits, allow_pickle = True)

    paras.inits = np.load(paras.split_fname0, allow_pickle = True)
    plot_inits = []
    for journey in paras.inits:
        for i in range(2):
            line = [journey[i][0],float(journey[i][1]), float(journey[i][2]), float(journey[i][3])]
            if i == 0:
                plot_inits.append([line])
            else:
                plot_inits[-1].append(line)
                
    paras.matrix = np.inf*np.ones((ncells, ncells))
    paras.matrix = update_matrix(paras.matrix, plot_inits)
    paras.plot_count = 0
    plotmat(paras.matrix, paras.start_time, paras.end_time, completes = plot_inits)
    printnice(plot_inits)
    savenice(plot_inits)
    paras.inits = plot_inits.copy()
    
    if not done1:
        ###################################
        #STEP 2: Find initial splits (with geographical restriction initially)
        #If station logs exist between these stations then proceed as normal -
        
        if not os.path.exists(paras.log_fname) or paras.ignore_log:  #No existing data for this particular journey, so do it from scratch
            paras.log_exists = False
            #At this point do a QUICK search on these stations - so only one page loaded from NR for each station. That should be adequate.
            init_stats = find_geog_splits(stats, paras.d_fact)
            print('%d Geographical Splits Determined, time taken %.2f s' % (len(init_stats), time.time() - timer_start))
            complete_init_splits(paras, stats, init_stats)  #This will do a quick version to generate the station log - THAT IS ALL
            
        #Then proceed with the new log
        paras.stat_log = np.load(paras.log_fname).tolist()
        paras.log_exists = True
        print('Loaded existing station log with', len(paras.stat_log), 'stations')
        init_stats = []
        #Filter out those stations which do not meet the time constraints
        for i in range(len(paras.stat_log)):
            if float(paras.stat_log[i][1]) <= base_tmax + paras.t_extra and len(init_stats) < paras.check_max:
                init_stats.append(paras.stat_log[i][0])
        complete_init_splits(paras, stats, init_stats)  #This will do a quick version to generate the station log - THAT IS ALL
        
        

def analyse1(paras, t_start = 1, t_end = 2359, pmax = 1e6):
    
    paras.complete1s = np.load(paras.split_fname1, allow_pickle = True)
    print(len(paras.complete1s), 'initial splits loaded')

    ncells = int(60*24/paras.matrix_res)
    paras.matrix = np.inf*np.ones((ncells, ncells))
    stats = station_info()

    # UPDATE PRICE MATRIX
    paras.matrix = update_matrix(paras.matrix, paras.complete1s)
    paras.stat_log = np.load(paras.log_fname).tolist()

    #FILTER SPLITS BASED ON THIS NEW MATRIX
    paras.filtered_completes = []
    ranks = []
    paras.base_tmax = 0
    
    #Have some kind of parameter to judge whether additional splits could be useful
    potentials = []
    potential_prices = []
    potential_prices_raw = []
    potential_times = []
    split_prices = []  #the maximum prices for each leg of the initial split
    d = stats.distance(paras.complete1s[0][0][0], paras.complete1s[0][-1][0])
    ppm0 = 1e6
    for complete in paras.complete1s:
        if len(complete) == 2:
            p1 = sum(np.array(complete)[:,3].astype(float))   #price point. Need to test this later.
            ppm0 = min(ppm0, p1/d)
    print('Min unsplit Price Per Mile', ppm0)

    ppm1 = 1e6
    alpha = 0.25
    for complete in paras.complete1s:
        add = True
        t0 = timediff(0.0, complete[0][2])
        t1 = timediff(0.0, complete[-1][1])
        cell1 = int(ncells*(t0-1)/(60*24))
        cell2 = int(ncells*t1/(60*24))
        p1 = sum(np.array(complete)[:,3].astype(float))   #price point. Need to test this later.
        
        if float(complete[0][2]) < t_start or float(complete[-1][1]) > t_end:
            add = False

        if timediff(complete[0][2], complete[-1][1]) > paras.base_tmax + paras.t_extra:
            add = False

        if len(complete) == 3 and add:
            d1 = stats.distance(complete[0][0], complete[1][0])
            d2 = stats.distance(complete[1][0], complete[-1][0])
            frac =  2*min(d1, d2)/d
            pp1 = complete[1][-1] + ppm0*d2/(frac**alpha)
            pp2 = complete[-1][-1] + ppm0*d1/(frac**alpha)
            ppw = max(pp1, pp2) - paras.matrix[cell1, cell2]   #Potential saving if going from this point. Need to prioritise mid-way stations though...
            pp1 = complete[1][-1] + ppm0*d2
            pp2 = complete[-1][-1] + ppm0*d1
            ppr = max(pp1, pp2) - paras.matrix[cell1, cell2]   #Potential saving if going from this point. Need to prioritise mid-way stations though...
            
            if complete[1][0] not in potentials:
                potentials.append(complete[1][0])
                potential_prices.append(ppw)
                potential_prices_raw.append(ppr)
                potential_times.append([complete[1][1],complete[1][2]])   #arrive after and leave before this time
                split_prices.append([complete[1][-1], complete[-1][-1]])
            else:
                ind = potentials.index(complete[1][0])
                potential_prices[ind] = min(ppw, potential_prices[ind])
                potential_prices_raw[ind] = min(ppw, potential_prices_raw[ind])
                potential_times[ind][0] = min(potential_times[ind][0], complete[1][1])
                potential_times[ind][1] = max(potential_times[ind][1], complete[1][2])
                split_prices[ind][0] = max(split_prices[ind][0], complete[1][-1])
                split_prices[ind][1] = max(split_prices[ind][1], complete[-1][-1])
                
            
            
        if not (p1 <= paras.matrix[cell1, cell2]):
            add = False
        if not (p1 < paras.matrix[cell1+1, cell2] and p1 < paras.matrix[cell1,cell2-1]):
            add = False
        
        if p1 > pmax:
            add = False
            
        if add and complete not in paras.filtered_completes:
            paras.filtered_completes.append(complete)
            ranks.append([t0*10000+t1,len(ranks)])
            ppm1 = min(ppm1, p1/d)

        if len(complete) == 2:
            paras.base_tmax = max(paras.base_tmax, timediff(complete[0][2], complete[1][1]))
            
    print('Avg. 1 split Price Per Mile', ppm1)
    print(potentials)
    #SORT THESE BASED ON DEPARTURE TIME
    ranks.sort() 
    order = np.array(ranks, dtype = 'int')[:,1].tolist()
    #np.sort(arglist)
    paras.filtered_completes = np.array(paras.filtered_completes, dtype = 'object')[order]
    plotmap(paras, stats)
    printnice(paras.filtered_completes)
    savenice(paras.filtered_completes)
    print(len(paras.filtered_completes), 'single splits remaining after filtering')
    paras.plot_count = 1
    plotmat(paras.matrix, paras.start_time, paras.end_time, completes = paras.filtered_completes)
    
    np.save('data/' + str(paras.start_station) + str(paras.end_station) + str(paras.day) + 'split1', paras.filtered_completes, allow_pickle = True)

    ##### DETERMINE SPLIT STATIONS WHICH HAVE THE POTENTIAL TO BE BETTER WITH FURTHER SPLITS
    
    paras.potentials = potentials
    paras.potential_prices = potential_prices
    paras.potential_prices_raw = potential_prices_raw
    paras.potential_times = potential_times
    paras.split_prices = split_prices
            
def advanced_split(paras):
    #Takes the 'potential' stations idendified by the last analyse step, and does a basic split in each direction from them.
    #Then matches to suitable unfiltered splits from stage one, and filters again
    second_dfact = 1.25
    if paras.quick:
        nstats_max = 5
        nchecks_max = 10
    else:
        nstats_max = 250
        nchecks_max = 25

    done2 = False
    if os.path.exists(paras.split_fname2) and not paras.redo2 and os.path.exists(paras.log_fname):
        print('Loading Existing Second Splits')
        done2 = True

    stat_inds = np.array(np.array(paras.potential_prices).argsort())
    potentials1 = np.array(paras.potentials)[stat_inds]
    potential_times = np.array(paras.potential_times)[stat_inds]

    stat_inds = np.array(np.array(paras.potential_prices_raw).argsort())
    potentials2 = np.array(paras.potentials)[stat_inds]

    #print('Check1s:', potentials1[:min(nstats_max, len(potentials1))])
    #print('Check2s:', potentials2[:min(nchecks_max, len(potentials2))])
    
    if not done2:

        stats = station_info()
        paras.stat_log = np.load(paras.log_fname).tolist()
        ncells = len(paras.matrix[0])
    
        #nstats2 = min(10, len(paras.stat_log)) #number of stations to check enroute. Could test using potentials instead? No particular reason why not...
        nstats2 = min(nstats_max, len(potentials1))

        print(nstats2, 'stations selected for further splitting:')
        print(potentials1[:nstats2])

        def advanced_split(paras, stats, stat_check, start_stat, end_stat, start_time, end_time, forwardback, i1):
            #Checks an individual ssplit forward split (splitting the second leg of the initial split). Do need additional time constraints...
            journeys_1 = find_journey_info(stats, start_stat, stat_check, paras.day, start_time, end_time)
            if len(journeys_1) > 0:
                journeys_2 = find_journey_info(stats, stat_check, end_stat, paras.day, journeys_1[0][1], paras.end_time)
                if len(journeys_1) > 0 and len(journeys_2) > 0:   #This is possible time-wise
                    for i, j2 in enumerate(journeys_2):
                        for j, j1 in enumerate(journeys_1):
                            if j2[0] > j1[1]:  #works time-wise
                                #ALSO CHECK AGAINST MIN PRICE HERE - HAVE TO BE FUSSY
                                complete = [[start_stat, start_time, j1[0],0.],[stat_check, j1[1], j2[0],j1[2]],[end_stat, j2[1], end_time,j2[2]] ]
                                p1 = sum(np.array(complete)[:,3].astype(float))  
                                if forwardback:   #is a forward split
                                    if p1 < paras.split_prices[i1][1]:
                                        partial2s.append(complete)     
                                else:
                                    if p1 < paras.split_prices[i1][0]:
                                        partial1s.append(complete)     
        complete2s = paras.complete1s.tolist()
           
        for i1, stat_main_log in enumerate(paras.stat_log[:nstats2]):
            stat_main = stat_main_log[0]
        #for i1, stat_main in enumerate(potentials1[:nstats2]):

            print('Current time taken', (time.time() - paras.time_start)/60.0, 'minutes')
            if (time.time() - paras.time_start)/60.0 > float(paras_import[8]):
                break
            #stat_main = stat[0]
            #Do forward splits first (splitting the last section)
            print('Checking intermediate station', i1+1, '/', nstats2, stat_main)
            #print('Times', paras.potential_times[i1])
            #print('Prices', paras.split_prices[i1])
            ##########################################################
            #NEED A TIME CHECK HERE AS IT CURRENTLY DOESN'T! CAN USE POTENTIALS
            #Then backward splits (splitting the first section)
            partial1s = []
            #nbases = min(50, len(paras.stat_log)) #number of stations to check enroute. Could test using potentials instead? No particular reason why not...
            nbases = min(nchecks_max, len(potentials2)) #number of stations to check enroute. Could test using potentials instead? No particular reason why not...
            threads = []
            
            d_ref = stats.distance(paras.start_station, stat_main)
            t0 = potential_times[i1][0]; t1 = potential_times[i1][1]
    
            t0 = paras.start_time; t1 = paras.end_time
            for j in range(0,nbases):
                #stat_check = potentials2[j]
                stat_check = paras.stat_log[j][0]
                dnew = stats.distance(stat_main, stat_check) + stats.distance(stat_check, paras.start_station)
                if dnew/d_ref < second_dfact:
    
                    x = threading.Thread(target=advanced_split, args=(paras, stats, stat_check, paras.start_station, stat_main,paras.start_time,t1,False,i1), daemon = False)
                    threads.append(x)
                    x.start()
            for j, x in enumerate(threads):
                x.join()
            
            paras.matrix = update_matrix(paras.matrix, complete2s)  #update matrix per intermediate station 
    
            #Attempt to pair up with existing completes, but only if this extra split is directly advantageous
            for old_complete in paras.complete1s:
                if old_complete[1][0] == stat_main and len(old_complete) == 3:
                    #This is potentially good. See if it matches up with anything new
                    for partial in partial1s:
                        #Check times
                        if partial[-1][1] <= old_complete[1][2]:
        
                            t0 = timediff(0.0, partial[0][2])
                            t1 = timediff(0.0, old_complete[-1][1])
                            cell1 = int(ncells*(t0-1)/(60*24))
                            cell2 = int(ncells*t1/(60*24))
                            p1 = partial[1][3] + partial[2][3] + old_complete[-1][3]
                            #print('Price', p1, 'necessary', paras.matrix[cell1,cell2])
                            if p1 < paras.matrix[cell1,cell2] and timediff(t0,t1) < paras.t_extra + paras.base_tmax:
                                complete2 = [partial[0],partial[1],old_complete[1].copy(),old_complete[2].copy()]
                                #complete2[1][2] = partial[0][2]
                                complete2s.append(complete2)
    
            #paras.matrix = update_matrix(paras.matrix, complete2s)  #update matrix per intermediate station 

            partial2s = []
            nbases = min(nchecks_max, len(potentials2)) #number of stations to check enroute
            threads = []
            t0 = paras.potential_times[i1][0]; t1 = paras.potential_times[i1][1]
            d_ref = stats.distance(stat_main, paras.end_station)
            
            t0 = paras.start_time; t1 = paras.end_time

            for j in range(0,nbases):
                #stat_check = potentials2[j]
                stat_check = paras.stat_log[j][0]

                #Do geographical check before clogging the requests
                dnew = stats.distance(stat_main, stat_check) + stats.distance(stat_check, paras.end_station)
                if dnew/d_ref < second_dfact:
                    x = threading.Thread(target=advanced_split, args=(paras, stats, stat_check, stat_main, paras.end_station,t0,paras.end_time,True,i1), daemon = False)
                    threads.append(x)
                    x.start()
            for j, x in enumerate(threads):
                x.join()
            
            #Attempt to pair up with existing completes, but only if this extra split is directly advantageous
            for old_complete in paras.complete1s:
                if old_complete[1][0] == stat_main and len(old_complete) == 3:
                    #This is potentially good. See if it matches up with anything new
                    for partial in partial2s:
                        #Check times
                        if partial[0][2] >= old_complete[1][1]:
        
                            t0 = timediff(0.0, old_complete[0][2])
                            t1 = timediff(0.0, partial[-1][1])
                            cell1 = int(ncells*(t0-1)/(60*24))
                            cell2 = int(ncells*t1/(60*24))
                            p1 = partial[1][3] + partial[2][3] + old_complete[1][3]
                            #print('Price', p1, 'necessary', paras.matrix[cell1,cell2])
                            if p1 < paras.matrix[cell1,cell2] and timediff(t0,t1) < paras.t_extra + paras.base_tmax:
                                complete2 = [old_complete[0].copy(),old_complete[1].copy(),partial[1].copy(),partial[2].copy()]
                                complete2[1][2] = partial[0][2]
                                complete2s.append(complete2)
                                
            paras.matrix = update_matrix(paras.matrix, complete2s)  #update matrix per intermediate station 
            
            #Attempt to pair up with partial1s that have been found for this split - for an extra step
            for partial1 in partial1s:
                for partial2 in partial2s:
                        #Check times
                        if partial2[0][2] >= partial1[2][1]:
                            t0 = timediff(0.0, partial1[0][2])
                            t1 = timediff(0.0, partial2[2][1])
                            cell1 = int(ncells*(t0-1)/(60*24))
                            cell2 = int(ncells*t1/(60*24))
                            p1 = partial1[1][3] + partial1[2][3] + partial2[1][3] + partial2[2][3]
                            if p1 < paras.matrix[cell1,cell2] and timediff(t0,t1) < paras.t_extra + paras.base_tmax:
                                complete2 = [partial1[0].copy(),partial1[1].copy(),partial1[2].copy(),partial2[1].copy(),partial2[2].copy()]
                                complete2[2][2] = partial2[0][2]
                                complete2s.append(complete2)
                                
            print(len(complete2s)-len(paras.complete1s), 'new splits found (not yet filtered)')
            paras.matrix = update_matrix(paras.matrix, complete2s)  #update matrix per intermediate station 
            #printnice(complete2s)
            
            if i1%5 == 0:
                paras.complete2_temp = np.array(complete2s, dtype = 'object')
                np.save(paras.split_fname2, paras.complete2_temp, allow_pickle = True)
                analyse2(paras, pmax = float(paras_import[6]), t_start = paras.start_time, t_end = paras.end_time)   #Prints the second splits and updates the overall pricing matrix

        paras.complete2s = np.array(complete2s, dtype = 'object')
        np.save(paras.split_fname2, paras.complete2s, allow_pickle = True)

def analyse2(paras, t_start = 1, t_end = 2359, pmax = 1e6):
    
    paras.complete2s = np.load(paras.split_fname2, allow_pickle = True).tolist()

    print(len(paras.complete2s), 'second splits loaded')

    ncells = int(60*24/paras.matrix_res)
    paras.matrix = np.inf*np.ones((ncells, ncells))
    stats = station_info()

    paras.stat_log = np.load(paras.log_fname).tolist()

    #FILTER SPLITS BASED ON THIS NEW MATRIX
    paras.filtered_completes = []
    ranks = []
    paras.base_tmax = 0
    
    #Have some kind of parameter to judge whether additional splits could be useful
    d = stats.distance(paras.complete2s[0][0][0], paras.complete1s[0][-1][0])
    ppm2 = 1e6
    
    # UPDATE PRICE MATRIX
    paras.matrix = update_matrix(paras.matrix, paras.complete2s)

    for complete in paras.complete2s:
        if len(complete) == 2:
            p1 = sum(np.array(complete)[:,3].astype(float))   #price point. Need to test this later.
            ppm2 = min(ppm2, p1/d)
            
    print('Min unsplit Price Per Mile', ppm2)

    ppm2 = 1e6
    for complete in paras.complete2s:
        add = True
        t0 = timediff(0.0, complete[0][2])
        t1 = timediff(0.0, complete[-1][1])
        cell1 = int(ncells*(t0-1)/(60*24))
        cell2 = int(ncells*t1/(60*24))
        p1 = sum(np.array(complete)[:,3].astype(float))   #price point. Need to test this later.
        
        if float(complete[0][2]) < t_start or float(complete[-1][1]) > t_end:
            add = False

        if timediff(complete[0][2], complete[-1][1]) > paras.base_tmax + paras.t_extra:
            add = False

        if not (p1 <= paras.matrix[cell1, cell2]):
            add = False
        if not (p1 < paras.matrix[cell1+1, cell2] and p1 < paras.matrix[cell1,cell2-1]):
            add = False
        
        if p1 > pmax:
            add = False
            
        if add and complete not in paras.filtered_completes:
            paras.filtered_completes.append(complete)
            ranks.append([t0*10000+t1,len(ranks)])
            ppm2 = min(ppm2, p1/d)

        if len(complete) == 2:
            paras.base_tmax = max(paras.base_tmax, timediff(complete[0][2], complete[1][1]))
            
    print('Min 2 split Price Per Mile', ppm2)

    #SORT THESE BASED ON DEPARTURE TIME
    ranks.sort() 
    order = np.array(ranks, dtype = 'int')[:,1].tolist()
    #np.sort(arglist)
    paras.filtered_completes = np.array(paras.filtered_completes, dtype = 'object')[order]
    plotmap(paras, stats)
    printnice(paras.filtered_completes)
    savenice(paras.filtered_completes)
    print(len(paras.filtered_completes), 'splits remaining after filtering')
    paras.plot_count = 2
    plotmat(paras.matrix, paras.start_time, paras.end_time, completes = paras.filtered_completes)
    
    np.save('data/' + str(paras.start_station) + str(paras.end_station) + str(paras.day) + 'split2', paras.filtered_completes, allow_pickle = True)

    
paras_import = np.loadtxt('parameters.txt', dtype = str)

paras = parameters(paras_import[0], paras_import[1], int(paras_import[2]), int(paras_import[3]), int(paras_import[4]), quick = int(paras_import[7]), t_extra = float(paras_import[6]), ignore_log = False, redo = False, redo2 = True)   #more parameters are in the 'parameters' class at the top
initial_split(paras)   #Does a (reasonably) comprehensive search of split stations
analyse1(paras, pmax = float(paras_import[6]), t_start = paras.start_time, t_end = paras.end_time)   #Prints the first splits and updates the overall pricing matrix
advanced_split(paras)  #Seeks to improve on the first splits by identifying potentially good stations
analyse2(paras, pmax = float(paras_import[6]), t_start = paras.start_time, t_end = paras.end_time)   #Prints the second splits and updates the overall pricing matrix
    
        
    
    
    
    
    
    
    
    
    
    
    
