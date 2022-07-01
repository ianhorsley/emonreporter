#!/usr/bin/env python

"""Heatmiser configurer from xml

Gets remote xml file, parses data and configures heatmiser stats.

"""

###TODO
# Add tests for XmlGetter
# Add logging

import requests
from time import mktime, strptime #strftime, localtime, 
import os #import stat, path, utime

from get_config import url, destfile, username, password

class XmlGetter(object):

    def __init__(self, username, password):
        """Setup an XmlGetter.

        """
        self.url = url
        self.username = username
        self.password = password

    def _get_headers(self, url):
        """Get the file headers without the body."""
        h = requests.head(url, allow_redirects=False, auth=(self.username,self.password))
        print h
        return h.headers

    def _get_file(self, url):
        """Get the file"""
        return requests.get(url, allow_redirects=False, auth=(self.username,self.password))

    @staticmethod
    def _is_downloadable(header):
        """Does the url contain a downloadable resource?"""
        content_type = header.get('content-type')
        if not 'xml' in content_type.lower():
            #raise FileNotFoundError("File not xml, credetials may be wrong.")
            raise IOError('file not accessible')

    
    @staticmethod
    def _has_changed(header, destfile):
        """Has the file changed compared to local file. Based on timestamp.
        If the local file does not exist then remote is different."""

        if not os.path.exists(destfile):
            print("file doesn't exist")
            return True
        localLastModified = os.stat(destfile).st_mtime

        srvLastModifiedStr = header.get("Last-Modified")
        srvLastModified = mktime(strptime(srvLastModifiedStr,
          "%a, %d %b %Y %H:%M:%S GMT"))
        print localLastModified, srvLastModified
        return not localLastModified == srvLastModified

    def check_file(self, url, destfile):
        """Checks whether file has changed and gets it if needed.
        Returns True if file was updated."""

        headers = self._get_headers(url)
        print headers

        #check if downloadable, and otherwise through exception
        self._is_downloadable(headers)
        if self._has_changed(headers, destfile):

            response = self._get_file(url)
            print("len ", len(response.content))
            open(destfile, 'wb').write(response.content)
            
            #modify timestamps on local file so that they match the collected file.
            srvLastModifiedStr = response.headers.get("Last-Modified")
            srvLastModified = mktime(strptime(srvLastModifiedStr,
              "%a, %d %b %Y %H:%M:%S GMT"))
            os.utime(destfile, (srvLastModified, srvLastModified))
            return True
            
        return False

if __name__ == "__main__":
    
    #create XmlGetter
    getter = XmlGetter(username, password)
    
    #run the file check and get ## should be in a try
    if getter.check_file(url, destfile):
        print("downloaded updated file")
    
    # create a new XML file with the results
    from xml.dom import minidom
    from datetime import datetime, timedelta
    from pythonrfc3339 import parse_datetime
    import itertools
    import pytz

    mydoc = minidom.parse(destfile)

    calendars = mydoc.getElementsByTagName('calendar')

    stats = mydoc.getElementsByTagName('stat')

    print(stats)

    def roundTime(dt=None, dateDelta=timedelta(minutes=15)):
        """Round a datetime object to a multiple of a timedelta
        dt : datetime.datetime object, default now.
        dateDelta : timedelta object, we round to a multiple of this, default 1 minute.
        Author: Thierry Husson 2012 - Use it as you want but don't blame me.
                Stijn Nevens 2014 - Changed to use only datetime objects as variables
        """
        roundTo = dateDelta.total_seconds()

        if dt == None : dt = datetime.now()
        seconds = (dt - dt.min).seconds
        # // is a floor division, not a comment on following line:
        rounding = (seconds+roundTo/2) // roundTo * roundTo
        return dt + timedelta(0,rounding-seconds,-dt.microsecond)

    def setfrost(temp):
        print "setting frost to %s"%(temp)
    def setholiday(hours, temp):
        print "setting holiday for %i hours and frost to %i"%(hours, temp)

    timestampnow = pytz.utc.localize(datetime.utcnow())
    print "timenow", timestampnow
    for stat in stats[0:5]:
        #through away past except most recent past
        #keep today plus 7 days, may be able to add 7th day stuff to start of today particularly if after last event today.
        #compute spacing between items
        #if more than 4 in day, order by shortest (including spacing to last entry to day before). Remove items as needed by moving temperatures forward.

        print stat.getElementsByTagName('name')[0].firstChild.data
        #get target data from xml elements
        targetholder = stat.getElementsByTagName('targets')
        targets = targetholder[0].getElementsByTagName('target')
        
        #convert to dictionary and parse_datetime, if not to beyond longest likely holiday length
        targetlist = [{'time': parse_datetime(target.attributes['time'].value), 'temp': target.firstChild.data} for target in targets if parse_datetime(target.attributes['time'].value) <= timestampnow + timedelta(days=16)]
        #remove all but one historic item
        inpast = sum(1 for target in targetlist if timestampnow > target['time'])
        if inpast > 0:
            del targetlist[:inpast-1]
        else:
            print "warning - no history - do something different"
            targetlist[0:0] = {''}

        #add spacing information, looking back to previous entry
        targetlist[0]['spacing'] = timedelta(days=1)
        for i in range(len(targetlist)-1):
            targetlist[i+1]['spacing'] = targetlist[i+1]['time'] - targetlist[i]['time']
        #add weekday inforamtion (this could be moved later)
        for i in range(len(targetlist)):
            targetlist[i]['weekday'] = targetlist[i]['time'].weekday()

        #print initial state list
        for target in targetlist:
            print target['time'].date(), target['time'].time(), target['temp'], target['spacing'], 'n', target['weekday']
        
        targetlist2 = []
        #reduce to 4 targets per day, pulls temps forward over shortest times to compress.
        #today needs fixing so doesn't include past items in count, because that can be pushed to day before
        for key, group in itertools.groupby(targetlist, key=lambda target:target['time'].date()):
            daytargets = list(group)
            #extra spacing to previous entries
            spacing = [target['spacing'] for target in daytargets]
            #sort by spacing smallest to largest
            gaps = sorted(list(enumerate(spacing)), key=lambda x: x[1])
            #extra enough entries to remove that will reduce to 4
            if key == timestampnow.date():
                #if today, prevent pulling fowards next and following items
                gapstoremove = [x[0] for x in gaps[2:max(0,len(daytargets)-4+2)]]
            else:
                gapstoremove = [x[0] for x in gaps[0:max(0,len(daytargets)-4)]]
            #print "gaps", key, gapstoremove
            
            for tid, target in enumerate(daytargets):
                if tid in gapstoremove:
                    #if target is one shortly after previous, pull temp forward, but don't add entry
                    targetlist2[-1]['temp'] = target['temp']
                else:
                    targetlist2.append(target)
        
        #print next version of state list
        #for target in targetlist2:
        #    print target['time'].date(), target['time'].time(), target['temp'], target['spacing'], 'n', target['weekday']
        
        #if no future data, set to frost stat with temp from most recent past
        if len(targetlist2) < 2:
            setfrost(targetlist2[0]['temp'])
            continue
        
        #if large gap to next event, set holiday and frost temp to suitable holding temperature
        if not targetlist2[1]['time'].date() == timestampnow.date() and targetlist2[1]['time'].time() - timestampnow.time() > timedelta(hours=24):
            td = targetlist2[1]['time'].time() - timestampnow.date()
            holidayhours = td.days * 24 + td.seconds//3600
            setholiday(holidayhours, targetlist2[0]['temp'])
        else:
            holidayhours = 0
        
        #work through each day (wrapping if no contents)
        #treat today differently
        i = 0
        #items, today, but after end of any holiday and after current time
        # today = [i for i in targetlist2 if i['time'].date() == timestampnow.date() and i['time'] >= timestampnow + timedelta(hours=holidayhours)]
        # if len(today) < 4:
            # #find items, within 7 days of end of any configured holiday
            # #same day of week
            # #time before now
            # futureday = [i for i in targetlist2 if not i['time'].date() == timestampnow.date() and i['time'] >= timestampnow + timedelta(hours=holidayhours) and i['time'] < timestampnow + timedelta(hours=holidayhours) + timedelta(days=7) and i['time'].time() < timestampnow.time() and i['time'].weekday() == timestampnow.weekday()]
            
            # print "ft", len(futureday), futureday, (4-len(today)+1), futureday[:4-len(today)+1]
            # today[0:0] = futureday[:4-len(today)+1]
       
        # print "today", today
        
        # for target in today:
            # print target['time'].date(), target['time'].time(), target['temp'], 'n', target['weekday']
        
        print "final list"
        
        for i in range(0, 7):
            daydatetime = timestampnow + timedelta(days=i)
            day = [target for target in targetlist2 if target['time'].date() == daydatetime.date() and target['time'] >= timestampnow + timedelta(hours=holidayhours)]
            if i == 0 and len(day) < 4: #if today add one past item
                day[0:0] = [{'time':timestampnow - timedelta(minutes=10), 'temp': targetlist2[0]['temp'], 'weekday': timestampnow.weekday()}]
                #bug when time very early in day, should auto shift to day before
                #if len = 4 should shift to day before  
            if len(day) < 4:
                #find items, within 7 days of end of any configured holiday
                #same day of week
                #time before first existing time
                futureday = [i for i in targetlist2 if not i['time'].date() == daydatetime.date() and i['time'] >= timestampnow + timedelta(hours=holidayhours) and i['time'] < timestampnow + timedelta(hours=holidayhours) + timedelta(days=7) and i['time'].time() < day[0]['time'].time() and i['time'].weekday() == timestampnow.weekday()]
                day[0:0] = futureday[:4-len(day)]

            for target in day:
                print target['time'].date(), target['time'].time(), target['temp'], 'n', target['weekday']
            
            
        # how to wrap entries from last days if any on to today?
        # how to handle holidays?
        # how to handle missing days?
        
        
        #print targetlist
        
        # for key, group in itertools.groupby(targetlist, key=lambda target:target[0].date()):
            # daytargets = list(group)
            # print "a", key, group
            
            # #todays items strip previous entries except current
            # if key == timestampnow.date() and len(daytargets) > 4:
                # for target in daytargets:
                    # print target[0].time(), target[1]
                # #count items in the past.
                # inpast = sum(1 for target in daytargets if timestampnow > target[0])
                # print "itemsinpast", inpast
                # del daytargets[:inpast-1]
                

            
            # #process items for later in the week. (might not deal with auto starts well)
            # #if close pull the temp forwards
            # if len(daytargets) > 4:
                # for target in daytargets:
                    # print target[0].time(), target[1]
                
                # #find the time differences between entries
                # spacing = [daytargets[i+1][0] - daytargets[i][0] for i in range(len(daytargets)-1)]
                # #order by entry lengths
                # print spacing
                # gaps = sorted(list(enumerate(spacing)), key=lambda x: x[1])
                # gapstoremove = gaps[0:max(1,len(daytargets)-4)]
                # gapstoremove.sort(key=lambda x: x[0], reverse=True)
                # print gapstoremove
                # for id, gap in gapstoremove:
                    # print "replace", id, daytargets[i:i+2], "with", daytargets[id][0], daytargets[id+1][1]
                    # daytargets[id:id+2] = [[daytargets[id][0], daytargets[id+1][1]]]
                    # print "dt", len(daytargets)
                # for target in daytargets:
                    # print target[0].time(), target[1]
            
            # difference = timedelta(minutes=15)
            # while len(daytargets) > 4 and difference < timedelta(hours=15):
                # print len(daytargets), range( len(daytargets) - 2, -1, -1)
                # for i in range( len(daytargets) - 2, -1, -1):
                    # print "l", i, i+1, daytargets[i+1][0] - daytargets[i][0]
                    # if daytargets[i+1][0] - daytargets[i][0] <= difference:
                        # daytargets[i:i+1] = [[daytargets[i][0], daytargets[i+1][1]]]
                
                # difference *= 2        
            
            
        #for target in targets[0:10]:
            #2018-11-10T05:15:00+00:00 
            #print datetime.strptime(target.attributes['time'].value, '%Y-%m-%dT%H:%M:%S%z')
            #print parse_datetime(target.attributes['time'].value)
            #print target.attributes['time'].value, target.firstChild.data
        
        
        
