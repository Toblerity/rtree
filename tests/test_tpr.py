from collections import namedtuple, defaultdict
from math import ceil

import unittest
import numpy as np

import os
from rtree.index import Index, Property, RT_TPRTree


class Cartesian(namedtuple("Cartesian", (
        "id", "time", "x", "y", "x_vel", "y_vel", "update_time",
        "out_of_bounds"))):
    __slots__ = ()

    def getX(self, t):
        return self.x + self.x_vel * (t - self.time)

    def getY(self, t):
        return self.y + self.y_vel * (t - self.time)

    def getXY(self, t):
        return self.getX(t), self.getY(t)

    def get_coordinates(self, t_now=None):
        return ((self.x, self.y, self.x, self.y),
                (self.x_vel, self.y_vel, self.x_vel, self.y_vel),
                self.time if t_now is None else (self.time, t_now))


class QueryCartesian(namedtuple("QueryCartesian", (
        "start_time", "end_time", "x", "y", "dx", "dy"))):
    __slots__ = ()

    def get_coordinates(self):
        return ((self.x - self.dx, self.y - self.dy,
                 self.x + self.dx, self.y + self.dy),
                (0, 0, 0, 0),
                (self.start_time, self.end_time))


def data_generator(
        dataset_size=100, simulation_length=10, max_update_interval=20,
        queries_per_time_step=5, min_query_extent=0.05, max_query_extent=0.1,
        horizon=20, min_query_interval=2, max_query_interval=10, agility=0.01,
        min_speed=0.0025, max_speed=0.0166, min_x=0, min_y=0, max_x=1, max_y=1,
):

    def create_object(id_, time, x=None, y=None):
        # Create object with random or defined x, y and random velocity
        if x is None:
            x = np.random.uniform(min_x, max_x)
        if y is None:
            y = np.random.uniform(min_y, max_y)
        speed = np.random.uniform(min_speed, max_speed)
        angle = np.random.uniform(-np.pi, np.pi)
        x_vel, y_vel = speed * np.cos(angle), speed * np.sin(angle)

        # Set update time for when out of bounds, or max interval
        for dt in range(1, max_update_interval + 1):
            if not (0 < x + x_vel * dt < max_x and 0 < y + y_vel * dt < max_y):
                out_of_bounds = True
                update_time = time + dt
                break
        else:
            out_of_bounds = False
            update_time = time + max_update_interval

        return Cartesian(id_, time, x, y, x_vel, y_vel, update_time,
                         out_of_bounds)

    objects = list()
    objects_to_update = defaultdict(set)
    for id_ in range(dataset_size):
        object_ = create_object(id_, 0)
        objects.append(object_)
        objects_to_update[object_.update_time].add(object_)
        yield "INSERT", 0, object_

    for t_now in range(1, simulation_length):
        need_to_update = ceil(dataset_size * agility)
        updated_ids = set()

        while need_to_update > 0 or objects_to_update[t_now]:
            kill = False
            if objects_to_update[t_now]:
                object_ = objects_to_update[t_now].pop()
                if object_ not in objects:
                    continue
                kill = object_.out_of_bounds
            else:
                id_ = np.random.randint(0, dataset_size)
                while id_ in updated_ids:
                    id_ = np.random.randint(0, dataset_size)
                object_ = objects[id_]

            updated_ids.add(object_.id)
            need_to_update -= 1

            yield "DELETE", t_now, object_

            if kill:
                x = y = None
            else:
                x, y = object_.getXY(t_now)
            object_ = create_object(object_.id, t_now, x, y)
            objects[object_.id] = object_
            objects_to_update[object_.update_time].add(object_)

            yield "INSERT", t_now, object_

        for _ in range(queries_per_time_step):
            x = np.random.uniform(min_x, max_x)
            y = np.random.uniform(min_y, max_y)
            dx = np.random.uniform(min_query_extent, max_query_extent)
            dy = np.random.uniform(min_query_extent, max_query_extent)
            dt = np.random.randint(min_query_interval, max_query_interval + 1)
            t = np.random.randint(t_now, t_now + horizon - dt)

            yield "QUERY", t_now, QueryCartesian(t, t + dt, x, y, dx, dy)


def intersects(x1, y1, x2, y2, x, y, dx, dy):
    # Checks if line from x1, y1 to x2, y2 intersects with rectangle with
    # bottom left at x-dx, y-dy and top right at x+dx, y+dy.
    # Implementation of https://stackoverflow.com/a/293052

    # Check if line points not both more/less than max/min for each axis
    if (x1 > x + dx and x2 > x + dx) or (x1 < x - dx and x2 < x - dx) \
            or (y1 > y + dy and y2 > y + dy) or (y1 < y - dy and y2 < y - dy):
        return False

    # Check on which side (+ve, -ve) of the line the rectangle corners are,
    # returning True if any corner is on a different side.
    calcs = ((y2 - y1) * rect_x + (x1 - x2) * rect_y + (x2 * y1 - x1 * y2)
             for rect_x, rect_y in ((x - dx, y - dy),
                                    (x + dx, y - dy),
                                    (x - dx, y + dy),
                                    (x + dx, y + dy)))
    sign = np.sign(next(calcs))  # First corner (bottom left)
    return any(np.sign(calc) != sign for calc in calcs)  # Check remaining 3


class TPRTests(unittest.TestCase):

    def test_tpr(self):
        # TODO : this freezes forever on some windows cloud builds
        if os.name == 'nt':
            return

        # Cartesians list for brute force
        objects = dict()
        tpr_tree = Index(properties=Property(type=RT_TPRTree))

        for operation, t_now, object_ in data_generator():
            if operation == "INSERT":
                tpr_tree.insert(object_.id, object_.get_coordinates())
                objects[object_.id] = object_
            elif operation == "DELETE":
                tpr_tree.delete(object_.id, object_.get_coordinates(t_now))
                del objects[object_.id]
            elif operation == "QUERY":
                tree_intersect = set(
                    tpr_tree.intersection(object_.get_coordinates()))

                # Brute intersect
                brute_intersect = set()
                for tree_object in objects.values():
                    x_low, y_low = tree_object.getXY(object_.start_time)
                    x_high, y_high = tree_object.getXY(object_.end_time)

                    if intersects(
                            x_low, y_low, x_high, y_high,  # Line
                            object_.x, object_.y, object_.dx, object_.dy):  # Rect
                        brute_intersect.add(tree_object.id)

                # Tree should match brute force approach
                assert tree_intersect == brute_intersect
