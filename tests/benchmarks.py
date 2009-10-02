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

from rtree import Rtree as _Rtree

TEST_TIMES = 20

# a very basic Geometry
class Point(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y

# Scatter points randomly in a 1x1 box
# 

class Rtree(_Rtree):
    pickle_protocol = -1

bounds = (0, 0, 6000000, 6000000)
count = 30000
points = []

insert_object = None
insert_object = {'a': range(100), 'b': 10, 'c': object(), 'd': dict(x=1), 'e': Point(2, 3)}

index = Rtree()
disk_index = Rtree('test', overwrite=1)

coordinates = []
for i in xrange(count):
    x = random.randrange(bounds[0], bounds[2]) + random.random()
    y = random.randrange(bounds[1], bounds[3]) + random.random()
    point = Point(x, y)
    points.append(point)

    index.add(i, (x, y), insert_object)
    disk_index.add(i, (x, y), insert_object)
    coordinates.append((i, (x, y, x, y), insert_object))

s ="""
bulk = Rtree(coordinates[:2000])
"""
t = timeit.Timer(stmt=s, setup='from __main__ import coordinates, Rtree, insert_object')
print "\nStream load:"
print "%.2f usec/pass" % (1000000 * t.timeit(number=TEST_TIMES)/TEST_TIMES)

s ="""
idx = Rtree()
i = 0
for point in points[:2000]:
    idx.add(i, (point.x, point.y), insert_object)
    i+=1
"""
t = timeit.Timer(stmt=s, setup='from __main__ import points, Rtree, insert_object')
print "\nOne-at-a-time load:"
print "%.2f usec/pass\n\n" % (1000000 * t.timeit(number=TEST_TIMES)/TEST_TIMES)


bbox = (1240000, 1010000, 1400000, 1390000)
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
print "%.2f usec/pass" % (1000000 * t.timeit(number=TEST_TIMES)/TEST_TIMES)

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
print "%.2f usec/pass" % (1000000 * t.timeit(number=TEST_TIMES)/TEST_TIMES)


if insert_object:
    s = """
        hits = disk_index.intersection(bbox, objects="raw")
        """
    t = timeit.Timer(stmt=s, setup='from __main__ import points, disk_index, bbox, insert_object')
    print "\nDisk-based Rtree Intersection without Item() wrapper (objects='raw'):"
    result = disk_index.intersection(bbox, objects="raw")
    print len(result), "raw hits"
    print "%.2f usec/pass" % (1000000 * t.timeit(number=TEST_TIMES)/TEST_TIMES)
    assert 'a' in result[0], result[0]

import os
try:
    os.remove('test.dat')
    os.remove('test.idx')
except:
    pass
