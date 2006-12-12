
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
count = 50000
points = []
index = Rtree()
for i in xrange(count):
    x = 360.0*(random.random()-0.5)
    y = 180.0*(random.random()-0.5)
    points.append(Point(x, y))
    index.add(i, (x, y))

bbox = (0.0, 50.0, 5.0, 55.0)

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

s = """
hits = [points[id] for id in index.intersection(bbox)]
"""
t = timeit.Timer(stmt=s, setup='from __main__ import points, index, bbox')
print "\nIntersection:"
print len([points[id] for id in index.intersection(bbox)]), "hits"
print "%.2f usec/pass" % (1000000 * t.timeit(number=100)/100)


