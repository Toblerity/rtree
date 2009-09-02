# Brute Force:
# 481 hits
# 29637.96 usec/pass
# 
# Memory-based Rtree Intersection:
# 481 hits
# 1216.70 usec/pass
# \Disk-based Rtree Intersection:
# 481 hits
# 2617.95 usec/pass

import random
import timeit

try:
    import pkg_resources
    pkg_resources.require('Rtree')
except:
    pass

from rtree import Rtree

# a very basic Geometry
class Point(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y

# Scatter points randomly in a 1x1 box
# 
minx = 0
miny = 0
maxx = 6000000
maxy = 6000000

bounds = (minx, miny, maxx, maxy)
count = 50000
points = []

#insert_object = None
insert_object = {'a': range(100), 'b': 10, 'c': object(), 'd': dict(x=1), 'e': Point(2, 3)}

# index = Rtree(properties = props)
index = Rtree()
disk_index = Rtree('test', overwrite=1)

for i in xrange(count):
    x = random.randrange(minx, maxx) * random.random()
    y = random.randrange(miny, maxy) * random.random()
    points.append(Point(x, y))

i = 0
coordinates = []
for point in points:
    index.add(i, (point.x, point.y))
    disk_index.add(i, (point.x,point.y))
    i+=1
    coordinates.append((i, (point.x, point.x, point.y, point.y), insert_object))

s ="""
bulk = Rtree(coordinates[0:2000])
"""
t = timeit.Timer(stmt=s, setup='from __main__ import coordinates, Rtree, insert_object')
print "\nStream load:"
print "%.2f usec/pass" % (1000000 * t.timeit(number=100)/100)

s ="""
idx = Rtree()
i = 0
for point in points[0:2000]:
    idx.add(i, (point.x, point.y), insert_object)
    i+=1
"""
t = timeit.Timer(stmt=s, setup='from __main__ import points, Rtree, insert_object')
print "\nOne-at-a-time load:"
print "%.2f usec/pass" % (1000000 * t.timeit(number=100)/100)


bbox = (240000, 130000, 400000, 350000)

print count, "points"
print "Query box: ", bbox
print ""

# Brute force all points within a 0.1x0.1 box
s = """
hits = [p for p in points if p.x >= bbox[0] and p.x <= bbox[2] and p.y >= bbox[1] and p.y <= bbox[3]]
"""
t = timeit.Timer(stmt=s, setup='from __main__ import points, bbox')
print "\nBrute Force:"
print len([p for p in points if p.x >= bbox[0] and p.x <= bbox[2] and p.y >= bbox[1] and p.y <= bbox[3]]), "hits"
print "%.2f usec/pass" % (1000000 * t.timeit(number=100)/100)

# 0.1x0.1 box using intersection

if insert_object is None:
    s = """
    hits = [points[id] for id in index.intersection(bbox)]
    """
else:
    s = """
    hits = [p.object for p in index.intersection(bbox, objects=insert_object)]
    """

t = timeit.Timer(stmt=s, setup='from __main__ import points, index, bbox, insert_object')
print "\nMemory-based Rtree Intersection:"
print len([points[id] for id in index.intersection(bbox)]), "hits"
print "%.2f usec/pass" % (1000000 * t.timeit(number=100)/100)


# run same test on disk_index.
s = s.replace("index.", "disk_index.")

t = timeit.Timer(stmt=s, setup='from __main__ import points, disk_index, bbox, insert_object')
print "\nDisk-based Rtree Intersection:"
print len(disk_index.intersection(bbox)), "hits"
print "%.2f usec/pass" % (1000000 * t.timeit(number=100)/100)

import os
try:
    os.remove('test.dat')
    os.remove('test.idx')
except:
    pass
