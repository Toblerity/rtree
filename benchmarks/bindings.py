"""Binding-layer benchmark for rtree.

Usage: python benchmarks/bindings.py [REPEAT]

Prints JSON ``{case: best_ms}`` (best of REPEAT runs, default 5).  Used to
compare the ctypes, C-API pybind11 and C++-API pybind11 bindings; see
docs/pybind11-port.md.
"""

import json
import random
import sys
import time

import numpy as np

from rtree import index

REPEAT = int(sys.argv[1]) if len(sys.argv) > 1 else 5
random.seed(1)
N = 100_000
Q = 20_000
boxes = []
for i in range(N):
    x, y = random.random() * 1000, random.random() * 1000
    boxes.append((x, y, x + random.random(), y + random.random()))
qs = []
for i in range(Q):
    x, y = random.random() * 1000, random.random() * 1000
    qs.append((x, y, x + 10, y + 10))
qmins = np.array([q[:2] for q in qs])
qmaxs = np.array([q[2:] for q in qs])
ids_arr = np.arange(N, dtype=np.int64)
bmins = np.array([b[:2] for b in boxes])
bmaxs = np.array([b[2:] for b in boxes])

results = {}


def bench(label, setup, fn):
    best = float("inf")
    for _ in range(REPEAT):
        state = setup()
        t0 = time.perf_counter()
        fn(state)
        best = min(best, time.perf_counter() - t0)
    results[label] = round(best * 1000, 1)


def build():
    return index.Index(((i, b, None) for i, b in enumerate(boxes)))


idx = build()
idx_obj = index.Index()
for i, b in enumerate(boxes[:20_000]):
    idx_obj.insert(i, b, obj=i)

noop = lambda: None  # noqa: E731


def insert_all(_):
    ix = index.Index()
    for i, b in enumerate(boxes):
        ix.insert(i, b)


def insert_obj(_):
    ix = index.Index()
    for i, b in enumerate(boxes[:20_000]):
        ix.insert(i, b, obj=i)


bench("insert 100k", noop, insert_all)
bench("insert w/ obj 20k", noop, insert_obj)
bench("stream bulk load 100k", noop, lambda _: build())
bench(
    "array bulk load 100k",
    noop,
    lambda _: index.Index((ids_arr, bmins, bmaxs)),
)
bench(
    "intersection ids 20k q",
    noop,
    lambda _: sum(len(list(idx.intersection(q))) for q in qs),
)
bench("count 20k q", noop, lambda _: sum(idx.count(q) for q in qs))
bench(
    "contains ids 20k q",
    noop,
    lambda _: sum(len(list(idx.contains(q))) for q in qs),
)
bench(
    "intersection objects 20k q",
    noop,
    lambda _: sum(len(list(idx.intersection(q, objects=True))) for q in qs),
)
bench(
    "intersection raw obj 20k q",
    noop,
    lambda _: sum(len(list(idx_obj.intersection(q, objects="raw"))) for q in qs),
)
bench(
    "nearest k=5 20k q",
    noop,
    lambda _: sum(len(list(idx.nearest(q, 5))) for q in qs),
)
bench(
    "nearest objects k=5 20k q",
    noop,
    lambda _: sum(len(list(idx.nearest(q, 5, objects=True))) for q in qs),
)
bench("intersection_v 20k", noop, lambda _: idx.intersection_v(qmins, qmaxs))
bench("nearest_v k=5 20k", noop, lambda _: idx.nearest_v(qmins, qmaxs, num_results=5))
bench("leaves()", noop, lambda _: idx.leaves())
bench("bounds x20k", noop, lambda _: [idx.bounds for _ in range(Q)])
bench(
    "delete 20k",
    build,
    lambda ix: [ix.delete(i, boxes[i]) for i in range(20_000)],
)


# Result-size sensitive cases: many hits per query, and paged queries.
idx_big = index.Index(((i, b, i) for i, b in enumerate(boxes)))
full = (0, 0, 1000, 1000)
bench(
    "objects=True, 100k hits x5",
    noop,
    lambda _: [len(list(idx_big.intersection(full, objects=True))) for _ in range(5)],
)
bench(
    "objects=raw, 100k hits x5",
    noop,
    lambda _: [len(list(idx_big.intersection(full, objects="raw"))) for _ in range(5)],
)
idx_big.result_limit = 10
bench(
    "paged objects (limit 10 of 100k) x100",
    noop,
    lambda _: [list(idx_big.intersection(full, objects=True)) for _ in range(100)],
)
bench(
    "paged ids (limit 10 of 100k) x100",
    noop,
    lambda _: [list(idx_big.intersection(full)) for _ in range(100)],
)

print(json.dumps(results))
