import numpy as np
import pytest

import rtree.index


def test_container():
    container = rtree.index.RtreeContainer()
    objects = list()

    # Insert
    boxes15 = np.genfromtxt('boxes_15x15.data')
    for coordinates in boxes15:
        objects.append(object())
        container.insert(objects[-1], coordinates)

    # Contains and length
    assert all(obj in container for obj in objects)
    assert len(container) == len(boxes15)

    # Delete
    for obj, coordinates in zip(objects, boxes15[:5]):
        container.delete(obj, coordinates)

    assert all(obj in container for obj in objects[5:])
    assert all(obj not in container for obj in objects[:5])
    assert len(container) == len(boxes15) - 5

    # Delete already deleted object
    with pytest.raises(IndexError):
        container.delete(objects[0], boxes15[0])

    # Insert duplicate object, at different location
    container.insert(objects[5], boxes15[0])
    assert objects[5] in container
    # And then delete it, but check object still present
    container.delete(objects[5], boxes15[0])
    assert objects[5] in container

    # Intersection
    obj = objects[10]
    results = container.intersection(boxes15[10])
    assert obj in results

    # Intersection with bbox
    obj = objects[10]
    results = container.intersection(boxes15[10], bbox=True)
    result = [result for result in results if result.object is obj][0]
    assert np.array_equal(result.bbox, boxes15[10])

    # Nearest
    obj = objects[8]
    results = container.intersection(boxes15[8])
    assert obj in results

    # Nearest with bbox
    obj = objects[8]
    results = container.nearest(boxes15[8], bbox=True)
    result = [result for result in results if result.object is obj][0]
    assert np.array_equal(result.bbox, boxes15[8])

    # Test iter method
    assert objects[12] in set(container)
