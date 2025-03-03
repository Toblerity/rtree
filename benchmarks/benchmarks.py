# hobu's latest results on his 2006-era machine

# Stream load:
# 293710.04 usec/pass
#
# One-at-a-time load:
# 527883.95 usec/pass
#
# 30000 points
# Query box:  (1240000, 1010000, 1400000, 1390000)
#
# Brute Force:
# 46 hits
# 13533.60 usec/pass
#
# Memory-based Rtree Intersection:
# 46 hits
# 7516.19 usec/pass
#
# Disk-based Rtree Intersection:
# 46 hits
# 7543.00 usec/pass
#
# Disk-based Rtree Intersection without Item() wrapper (objects='raw'):
# 46 raw hits
# 347.60 usec/pass

import random
import timeit
from pathlib import Path

import rtree
from rtree import Rtree as _Rtree

print(f"Benchmarking Rtree-{rtree.__version__} from {Path(rtree.__file__).parent}")
print(f"Using {rtree.core.rt._name} version {rtree.core.rt.SIDX_Version().decode()}")
print()

TEST_TIMES = 20


class Point:
    """A very basic Geometry."""

    def __init__(self, x, y):
        self.x = x
        self.y = y


class Rtree(_Rtree):
    pickle_protocol = -1


# Scatter points randomly in a 1x1 box
bounds = (0, 0, 6000000, 6000000)
count = 30000
points = []

insert_object = None
insert_object = {
    "a": list(range(100)),
    "b": 10,
    "c": object(),
    "d": dict(x=1),
    "e": Point(2, 3),
}

index = Rtree()
disk_index = Rtree("test", overwrite=1)

coordinates = []
random.seed("Rtree", version=2)
for i in range(count):
    x = random.randrange(bounds[0], bounds[2]) + random.random()
    y = random.randrange(bounds[1], bounds[3]) + random.random()
    point = Point(x, y)
    points.append(point)

    index.add(i, (x, y), insert_object)
    disk_index.add(i, (x, y), insert_object)
    coordinates.append((i, (x, y, x, y), insert_object))

s = """
bulk = Rtree(coordinates[:2000])
"""
t = timeit.Timer(stmt=s, setup="from __main__ import coordinates, Rtree, insert_object")
print("Stream load:")
print(f"{1e6 * t.timeit(number=TEST_TIMES) / TEST_TIMES:.2f} usec/pass")
print()

s = """
idx = Rtree()
i = 0
for point in points[:2000]:
    idx.add(i, (point.x, point.y), insert_object)
    i+=1
"""
t = timeit.Timer(stmt=s, setup="from __main__ import points, Rtree, insert_object")
print("One-at-a-time load:")
print(f"{1e6 * t.timeit(number=TEST_TIMES) / TEST_TIMES:.2f} usec/pass")
print()

bbox = (1240000, 1010000, 1400000, 1390000)
print(count, "points")
print("Query box: ", bbox)
print()

# Brute force all points within a 0.1x0.1 box
s = """
hits = [p for p in points
        if p.x >= bbox[0] and p.x <= bbox[2]
        and p.y >= bbox[1] and p.y <= bbox[3]]
"""
t = timeit.Timer(stmt=s, setup="from __main__ import points, bbox")
print("Brute Force:")
print(
    len(
        [
            p
            for p in points
            if p.x >= bbox[0] and p.x <= bbox[2] and p.y >= bbox[1] and p.y <= bbox[3]
        ]
    ),
    "hits",
)
print(f"{1e6 * t.timeit(number=TEST_TIMES) / TEST_TIMES:.2f} usec/pass")
print()

# 0.1x0.1 box using intersection

if insert_object is None:
    s = """
hits = [points[id] for id in index.intersection(bbox)]
    """
else:
    s = """
hits = [p.object for p in index.intersection(bbox, objects=insert_object)]
    """

t = timeit.Timer(
    stmt=s, setup="from __main__ import points, index, bbox, insert_object"
)
print("Memory-based Rtree Intersection:")
print(len([points[id] for id in index.intersection(bbox)]), "hits")
print(f"{1e6 * t.timeit(number=100) / 100:.2f} usec/pass")
print()

# run same test on disk_index.
s = s.replace("index.", "disk_index.")

t = timeit.Timer(
    stmt=s, setup="from __main__ import points, disk_index, bbox, insert_object"
)
print("Disk-based Rtree Intersection:")
hits = list(disk_index.intersection(bbox))
print(len(hits), "hits")
print(f"{1e6 * t.timeit(number=TEST_TIMES) / TEST_TIMES:.2f} usec/pass")
print()

if insert_object:
    s = """
hits = disk_index.intersection(bbox, objects="raw")
        """
    t = timeit.Timer(
        stmt=s, setup="from __main__ import points, disk_index, bbox, insert_object"
    )
    print("Disk-based Rtree Intersection without Item() wrapper (objects='raw'):")
    result = list(disk_index.intersection(bbox, objects="raw"))
    print(len(result), "raw hits")
    print(f"{1e6 * t.timeit(number=TEST_TIMES) / TEST_TIMES:.2f} usec/pass")
    assert "a" in result[0], result[0]  # type: ignore

Path("test.dat").unlink()
Path("test.idx").unlink()
