import math
from itertools import permutations

import util
from entities import Path

dist_cache = {}

def get_distance(p1, p2):
    """
    Returns the distance between two points. This is cached since it is expected that there will
    be a limited number of points used.
    """
    
    if dist_cache.get(f'{p1.toTuple()}, {p2.toTuple()}'):
        return dist_cache[f'{p1.toTuple()}, {p2.toTuple()}']
    elif dist_cache.get(f'{p2.toTuple()}, {p1.toTuple()}'):
        return dist_cache[f'{p2.toTuple()}, {p1.toTuple()}']
    try:
        path_to_passenger_raw = util.find_path_between_points_in_osrm(p1.toTuple(), p2.toTuple())
        dist_cache[f'{p1.toTuple()}, {p2.toTuple()}'] = path_to_passenger_raw
        return path_to_passenger_raw
    except Exception:
        dist_cache[f'{p1.toTuple()}, {p2.toTuple()}'] = None
        return None

def sort_path_brute(src, passengers):
    with_index = zip(range(len(passengers)), passengers)
    least_distance = math.inf
    best_order = None
    start_index = 0
    for order in permutations(with_index):
        total_distance = 0
        cur_point = src
        for index, p in order:
            dst_point = p.dest
            path_to_passenger_raw = get_distance(cur_point, dst_point)
            if path_to_passenger_raw is None:
                total_distance = math.inf
                break
            path_to_passenger = Path(*path_to_passenger_raw + [dst_point.toTuple()])
            total_distance += path_to_passenger.getDistance()
            cur_point = p.dest
        if total_distance < least_distance:
            least_distance = total_distance
            best_order = [p for i,p in order]
            start_index = order[0][0]
    return best_order, start_index