import datetime
import time

#
# Simple utility for printing the last 5 arguments for ubv2h264,
# which represent the date and the time range to extract.
#
# Edit the last line of this file to change the date/time
#

def print_args(year, month, day, hour, minute, minutes):
    d = datetime.datetime(year, month, day, hour, minute)
    d2 = d + datetime.timedelta(minutes=minutes)
    t = time.mktime(d.timetuple())
    t2 = time.mktime(d2.timetuple())
    print("%d %02d %02d %d %d" % (year, month, day, t*1000, t2*1000))

if __name__ == '__main__':
    # year, month, day, hour, minute, # of minutes to extract
    print_args(2021, 4, 8, 10, 30, 10)
