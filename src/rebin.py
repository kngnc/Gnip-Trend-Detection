#!/usr/bin/env python

"""
The script reads in data in the format: 
 [time_stamp] [rule] [rule_count] [total_count] [interval_duration_in_sec] 
Data are read from a file. 

Inputs are:
    rule name
    start time
    stop time
    bin size

Output is a .pkl of the list of (TimeBucket,count) pairs.

Rebinning logic looks like:
    assign intervals to a bin
    when the interval is split over two bins:
        assume constant rate over the interval and split count b/n bins

"""

import sys
import datetime
import argparse
import collections
import operator
import pickle

import models
from time_bucket import TimeBucket

EXPLICIT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"
COMPACT_DATETIME_FORMAT = "%Y%m%d%H%M%S"

parser = argparse.ArgumentParser()
parser.add_argument("-a",dest="start_time",default="20141210000000",help="YYYYMMDDhhmmss") 
parser.add_argument("-o",dest="stop_time",default="20141211000000",help="YYYYMMDDhhmmss") 
parser.add_argument('-b',dest='binning_unit',action='store',default='seconds') 
parser.add_argument('-n',dest='n_binning_unit',action='store',default=60,type=int,help='number of binning units per bin') 
parser.add_argument("-i",dest="input_file_names",default=None, nargs="*")   
parser.add_argument("-f",dest="output_file_name",default="output.pkl")   
parser.add_argument("-r",dest="rule_name",type=str,default=None)   
parser.add_argument("-v",dest="verbose",type=bool,default=False)   

args = parser.parse_args()

if args.rule_name is None:
    sys.stderr.write("Rule name must be set with -r option\n")
    sys.exit(1)

if args.input_file_names is None:
    sys.stderr.write("Input file(s) must be specified. Exiting.")
    sys.exit(1)

start_time = datetime.datetime.strptime(args.start_time,COMPACT_DATETIME_FORMAT)
stop_time = datetime.datetime.strptime(args.stop_time,COMPACT_DATETIME_FORMAT) 

data = []

# put the data into a list of (TimeBucket, count) tuples
for input_file_name in args.input_file_names:
    f = open(input_file_name)
    for line in f:
        line_split = line.split(",")
        if line_split[1].strip() != args.rule_name.strip():
            continue
        else:
            this_stop_time = datetime.datetime.strptime(line_split[0],EXPLICIT_DATETIME_FORMAT)  
            if this_stop_time > stop_time:
                continue
            dt = datetime.timedelta(seconds=int(float(line_split[4])))
            this_start_time = this_stop_time - dt
            if this_start_time < start_time:
                continue
            time_bucket = TimeBucket(this_start_time, this_stop_time, EXPLICIT_DATETIME_FORMAT) 
            
            # sanity check: input time buckets must always be smaller than output time bucket
            if time_bucket.size() > datetime.timedelta(**{args.binning_unit:args.n_binning_unit}):
                sys.stderr.write("Input time bucket {} is larger that {}{}\n".format(time_bucket,str(args.n_binning_unit),args.binning_unit))
                sys.exit(-1)
            count = line_split[2]
            my_tuple = time_bucket, count
            data.append(my_tuple)

data_sorted = sorted(data)

# make a grid with appropriate bin size
tb_stop_time = start_time + datetime.timedelta(**{args.binning_unit:args.n_binning_unit})
tb = TimeBucket(start_time,tb_stop_time)

# make list of TimeBuckets for bins
grid = []
while tb.stop_time <= stop_time:
    grid.append(tb)
    tb_start_time = tb.stop_time
    tb_stop_time = tb_start_time + datetime.timedelta(**{args.binning_unit:args.n_binning_unit})
    tb = TimeBucket(tb_start_time,tb_stop_time)

# add data to a dictionary with indicies mapped to the grid indicies
final_data = collections.defaultdict(int)
for orig_tb,orig_count in data_sorted:
    for grid_tb in grid:
        idx = grid.index(grid_tb) 
        if orig_tb in grid_tb:
            final_data[idx] += int(orig_count)
            break
        elif orig_tb.intersects(grid_tb):
            frac = orig_tb.get_fraction_overlapped_by(grid_tb) 
            final_data[idx] += int(int(orig_count) * frac)
            # decide where to put the remainder of this orig_count
            if orig_tb.lowerlaps(grid_tb):
                final_data[idx-1] += int(int(orig_count) * (1-frac))
            elif orig_tb.upperlaps(grid_tb):
                final_data[idx+1] += int(int(orig_count) * (1-frac)) 
            else:
                sys.stderr.write("bad logic in rebinning; check input and output bin sizes. Exiting!\n")
                sys.exit(-1)

            break
        else:
            pass

final_sorted_data_tuples = []
for idx,count in sorted(final_data.items(), key=lambda x: grid[int(operator.itemgetter(0)(x))]):
    dt = grid[idx]
    final_sorted_data_tuples.append((dt,count))
    if args.verbose:
        sys.stdout.write("{} {}\n".format(dt,count))

pickle.dump(final_sorted_data_tuples,open(args.output_file_name,"w"))


