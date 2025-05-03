"""
Helper functions that are used in generating actual scenarios.
"""

import random

import config
import entities
import util

from util import NoRoute

def get_random(min, max):
    return min + random.random() * (max - min)

def gen_random_point():
    "Returns a random point in the map. It is likely you will NOT be using this directly."

    x = util.get_random(config.TOP_LEFT_X, config.BOT_RIGHT_X)
    y = util.get_random(config.BOT_RIGHT_Y, config.TOP_LEFT_Y)
    return entities.Point(x, y)

def gen_random_valid_point():
    "Returns a random point in the map that is on the road"

    point_raw = gen_random_point()
    point = entities.Point(*util.find_nearest_point_in_osrm_path(point_raw.x, point_raw.y))
    return point

def get_valid_points(points):
    "Returns a list of valid points based on provided list. Each point in the list must be in (y,x)"
    return [entities.Point(*util.find_nearest_point_in_osrm_path(p[1], p[0])) for p in points]

def get_random_valid_point(points):
    "Returns a random point that is based from the provided list. Each point in the list must be in (y,x)"

    point_raw = random.choice(points)
    point = entities.Point(*util.find_nearest_point_in_osrm_path(point_raw[1], point_raw[0]))
    return point

def gen_random_bnf_roam_path():
    "Returns a back-n-forth path in the map"

    while True:
        point_1 = gen_random_valid_point()
        point_2 = gen_random_valid_point()

        try:
            # must have p1 -> p2
            util.find_path_between_points_in_osrm(point_1.toTuple(), point_2.toTuple())
            # must have p2 -> p1
            util.find_path_between_points_in_osrm(point_2.toTuple(), point_1.toTuple())

            return entities.Cycle(point_1, point_2)
        except NoRoute:
            continue

def gen_random_bnf_roam_path_with_points(*points):
    "Returns a back-n-forth path that contains the points"

    if len(points) == 0:
        return gen_random_bnf_roam_path()
    elif len(points) == 1:
        while True:
            point_1 = points[0]
            point_2 = gen_random_point()

            try:
                # must have p1 -> p2
                util.find_path_between_points_in_osrm(point_1.toTuple(), point_2.toTuple())
                # must have p2 -> p1
                util.find_path_between_points_in_osrm(point_2.toTuple(), point_1.toTuple())

                return entities.Cycle(point_1, point_2)
            except NoRoute:
                continue
    elif len(points) == 2:
        util.find_path_between_points_in_osrm(points[0].toTuple(), points[1].toTuple())
        util.find_path_between_points_in_osrm(points[1].toTuple(), points[0].toTuple())
        return entities.Cycle(points[0], points[1])
    else:
        for i in range(len(points)-1):
            util.find_path_between_points_in_osrm(points[i].toTuple(), points[i+1].toTuple())
            util.find_path_between_points_in_osrm(points[i+1].toTuple(), points[i].toTuple())
        return entities.Cycle(points[0], points[1])
