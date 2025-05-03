import json
import util
from enum import Enum

MS_PER_FRAME = 1000

class NoMorePassengers(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def toTuple(self):
        return [self.x, self.y]
    
    def toJSON(self):
        return {
            "type": "point",
            "data": [self.x, self.y]
        }
    
    def __repr__(self):
        return json.dumps(self.toJSON())

class Path:
    def __init__(self, *args):
        self.path = [Point(*p) for p in args]
    
    def toJSON(self):
        return {
            "type": "path",
            "data": self.path.toJSON()
        }
    
    def __str__(self):
        return '-'.join([str(p) for p in self.path])
    
    def __repr__(self) -> str:
        return json.dumps(self.toJSON())

    def start(self):
        return self.path[0]
    
    def end(self):
        return self.path[-1]
    
    def getDistance(self):
        res = 0
        curPoint = self.path[0]
        for nxtPoint in self.path[1:]:
            res += util.get_euclidean_distance(curPoint.toTuple(), nxtPoint.toTuple())
            curPoint = nxtPoint
        return res

class Cycle:
    def __init__(self, *args):
        assert len(args) > 1, f"Found {len(args)} points. Cycle must have at least 2 points"
        self.path = [*args]
    
    def toJSON(self):
        return {
            "type": "cycle",
            "data": [x.toJSON() for x in self.path]
        }
    
    def getStartPoint(self):
        return self.path[0]
    
    def getNearestPointIndex(self, other):
        points_with_dist = list(map(
                                lambda index: (
                                    util.get_euclidean_distance(
                                        other.toTuple(), self.path[index].toTuple()
                                    ), index), 
                                range(len(self.path))
                            ))
        return min(points_with_dist)[1]
    
    def getNextPoint(self, other):
        curIndex = self.getNearestPointIndex(other)
        nxtIndex = (curIndex + 1) % len(self.path)
        return self.path[nxtIndex]

    def __repr__(self) -> str:
        return json.dumps(self.toJSON())

class Map:
    def __init__(
            self,
            x_min,
            y_min,
            x_max,
            y_max,
            num_row,
            num_col
    ):
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        self.num_row = num_row
        self.num_col = num_col

        # generate the grids
        self.grid_length = (x_max - x_min) / num_col
        self.grid_height = (y_max - y_min) / num_row

        # use a dictionary since we expect the map
        # to be sparsed
        self.grid = dict()
    
    def add(self, loc, obj):
        cell = self.grid.get(loc, [])
        cell.append(obj)
        self.grid[loc] = cell
    
    def rem(self, loc, obj):
        cell = self.grid.get(loc, [])
        cell = list(filter(lambda x: x != obj, cell))
        self.grid[loc] = cell
    
    def get_loc(self, x, y):
        cell_x = int((x -self.x_min) / self.grid_length)
        cell_y = int((y - self.y_min) / self.grid_height)

        # return a tuple so that it is immutable
        return (cell_x, cell_y)

    def same_loc(self, x1, y1, x2, y2):
        return self.get_loc(x1, y1) == self.get_loc(x2, y2)
    
    def get_cell(self, loc):
        return self.grid.get(loc, [])

class Actor:
    """
    A general purpose entity that appears on the visualizer. Contains metadata to aid in 
    visualization.
    """

    def __init__(
            self,
            createTime: int,
            deathTime: int
    ):
        self.createTime = createTime
        self.deathTime = deathTime

        # the actual path that will be parsed by the visualizer
        # should contain Points, not [x, y]
        self.path = []

        # the actual events which will be parsed by the visualizer
        self.events = []

class PassengerStatus(Enum):
    WAITING = 0
    ENQUEUED = 1
    ONBOARD = 2
    COMPLETED = 3

class Passenger(Actor):
    def __init__(
            self, 
            id,
            src: Point, 
            dest: Point,
            createTime: int,
            deathTime: int,
            status: PassengerStatus = PassengerStatus.WAITING
    ):
        super().__init__(createTime, deathTime)
        self.id = id
        self.src = src
        self.dest = dest
        self.status = status
        self.offloadTime = -1

        self.path.append(self.src)
    
    def toJSON(self):
        return {
            "id": self.id,
            "type": "passenger",
            "src": self.src.toJSON(),
            "dst": self.dest.toJSON(),
            "createTime": self.createTime,
            "deathTime": self.deathTime,
            "offloadTime": self.offloadTime,
            "path": [p.toJSON() for p in self.path]
        }

    def __str__(self):
        return f'P[{self.src} to {self.dest}]'

    def __repr__(self) -> str:
        return json.dumps(self.toJSON())

class Tricycle(Actor):
    """
    The tricycle should be able to:
        1. Roam - it can run continuously without a starting and end point
        2. Point-to-Point - it can run starting from a point and end at another point
        3. Pickup multiple passengers - it should be able to determine where each passengers need to go down
    """
    def __init__(
            self,
            id,
            capacity: int,
            speed: float,
            roamPath: Cycle | None,
            isRoaming: bool,
            startX: float,
            startY: float,
            createTime: int,
            deathTime: int,
            scheduler = None,
            map: Map | None = None,
            useMeters: bool = False
    ):
        super().__init__(createTime, deathTime)
        self.id = id
        if map:
            self.map = map

        # define the tricycle's physical characteristics
        self.capacity = capacity
        self.speed = speed
        self.active = True
        self.useMeters = useMeters
        
        # define the tricycle's driving behaviour
        self.roamPath = roamPath
        self.scheduler = scheduler

        # initialize the tricycle
        self.isRoaming = isRoaming
        self.x = startX
        self.y = startY
        self.passengers = []

        # initialize metrics
        self.totalDistance = 0
        self.totalProductiveDistance = 0
        self.totalDistanceM = 0
        self.totalProductiveDistanceM = 0
        self.waitingTime = 0

        # for queueing the locations to process
        self.to_go = []

        # add the starting path
        self.path.append(Point(self.x, self.y))
        self.events.append({
            "type": "APPEAR"
        })
    
    def toJSON(self):
        return {
                "id": self.id,
                "type": "trike",
                "speed": self.speed,
                "roamPath": self.roamPath.toJSON() if self.isRoaming else "None",
                "isRoaming": self.isRoaming,
                "startX": self.x,
                "startY": self.y,
                "passengers": [p.toJSON() for p in self.passengers],
                "createTime": self.createTime,
                "deathTime": self.deathTime,
                "totalDistance": self.totalDistance,
                "productiveDistance": self.totalProductiveDistance,
                "totalDistanceM": self.totalDistanceM,
                "totalProductiveDistanceM": self.totalProductiveDistanceM,
                "waitingTime": self.waitingTime,
                "path": [p.toJSON() for p in self.path],
                "events": self.events
        }

    def __repr__(self) -> str:
        return json.dumps(self.toJSON())

    def curPoint(self) -> Point:
        return self.path[-1]
    
    def loadNextCyclePoint(self):
        """
        This will attempt to add the next point in the cycle to the to-go list. 
        """

        curPoint = self.path[-1]
        nxtPoint = self.roamPath.getNextPoint(curPoint)
        self.addToGo(nxtPoint)
    
    def hasPassenger(self):
        return len(self.passengers) > 0
    
    def loadPassenger(self, p: Passenger):
        """
        Attempts to load a passenger and include it into its queue. If there is no more space,
        nothing will happen.
        """
        
        if len(self.passengers) >= self.capacity:
            return False
        self.events.append({
            "type": "LOAD",
            "data": p.id
        })
        self.events.append({
            "type": "WAIT",
            "data": 500
        })
        self.passengers.append(p)
        p.status = PassengerStatus.ONBOARD
        return True
    
    def processNextPassenger(self):
        """
        Schedules the next passenger to offload by OVERLOADING the current route
        and WITHOUT removing the passenger from the passenger queue. These are important
        since it may be possible to take in a new passenger that should be prioritized.

        Returns the time it takes to go directly to the passenger's destination.
        """
        
        if len(self.passengers) == 0:
            raise NoMorePassengers
        
        # for simplicity, just get the next passenger
        # passengers aren't deleted because it may be possible that 
        # the passenger won't be the next to be offloaded
        if self.scheduler is None:
            print("no scheduler", flush=True)
            p = self.passengers[0]
            # del self.passengers[0]
        else:
            index, p = self.scheduler(self.path[-1], self.passengers)
            # self.passengers.pop(index)

        src_point = self.path[-1]
        dst_point = p.dest
        try:
            path_to_passenger_raw = util.find_path_between_points_in_osrm(src_point.toTuple(), dst_point.toTuple()) + [dst_point.toTuple()]
        except util.NoRoute:
            print(f"No Route. Ignoring {p.id} going to {dst_point.toTuple()}")
            return None

        # trike doesn't move
        if len(path_to_passenger_raw) < 3:
            return None
        
        path_to_passenger = Path(*path_to_passenger_raw)

        # prepare the next paths and ignore current loc
        # we replace the to_go to emphasize that the trike is changing
        # where it will go now
        # loaded midway
        self.to_go = [Point(*p) for p in path_to_passenger_raw[1:]]

        return p

    def tryOffload(self):
        """
        Attempts to drop a passenger at the current grid. If a passenger was dropped,
        the tricycle will wait 500ms to simulate waiting for passengers to offload
        properly.
        """
        
        if not self.map:
            raise Exception("Not backward compatible. Please use a map")
        
        cur = self.path[-1]
        loc = self.map.get_loc(cur.x, cur.y)

        # check first if there are passengers to offlod
        dropped = False

        for index, p in enumerate(self.passengers[:]):
            p_loc = self.map.get_loc(p.dest.x, p.dest.y)
            # print("checking", p.id, loc, flush=True)*
            if p_loc == loc:
                dropped = True
                self.events.append({
                    "type": "DROP-OFF",
                    "data": p.id
                })
                self.passengers = list(filter(lambda x : x.id != p.id, self.passengers))
                p.status = PassengerStatus.COMPLETED
                print("dropped", p.id, loc, flush=True)
                yield p
        if dropped:
            self.events.append({
                "type": "WAIT",
                "data": 500
            })

    def checkPassengers(self):
        """
        Checks of there are passengers that can be loaded in the current grid.

        Returns an array of Passengers.
        """
        
        if not self.map:
            raise Exception("Not backward compatible. Please use a map")
        
        cur = self.path[-1]
        loc = self.map.get_loc(cur.x, cur.y)
        
        # check if there are passengers to load
        cell = self.map.get_cell(loc)        
        loaded = []
        for p in cell:
            if self.loadPassenger(p):
                loaded.append(p)
                self.map.rem(loc, p)
        return loaded

    def moveTrike(self):
        """
        Attempts to move the trike towards the next point in the to_go queue. If the next point is
        too far using the current speed to be reached immediately, the tricycle will only move to
        where it can reach.

        Returns the time taken in moving.
        """

        if not self.map:
            raise Exception("Not backward compatible. Please use a map")
        
        cur = self.path[-1]
        
        # move to next position
        if not self.to_go:
            return
        
        nxt = self.to_go[0]

        if self.useMeters:
            distRequiredM = util.haversine(*cur.toTuple(), *nxt.toTuple())
            distTravelledM = min(distRequiredM, self.speed)
            distRequired = distRequiredM
            distTravelled = distTravelledM
        else:
            distRequired = util.get_euclidean_distance(cur.toTuple(), nxt.toTuple())
            distRequiredM = util.haversine(*cur.toTuple(), *nxt.toTuple())
            distTravelled = min(distRequired, self.speed * MS_PER_FRAME)
            distTravelledM = 0 if distRequired == 0 else distRequiredM * (distTravelled/distRequired)

        if distRequired == 0:
            del self.to_go[0]
            return 0

        progress = min(distTravelled/distRequired, 1)
        new_point_raw = util.interpolate_points(cur.toTuple(), nxt.toTuple(), progress)
        self.path.append(Point(*new_point_raw))

        # update metrics
        self.totalDistance += distTravelled
        self.totalDistanceM += distTravelledM
        if self.hasPassenger():
            self.totalProductiveDistance += distTravelled
            self.totalProductiveDistanceM += distTravelledM

        if self.events and self.events[-1].get("type", "") == "MOVE":
            self.events[-1]["data"] += 1
        else:
            self.events.append({
                "type": "MOVE",
                "data": 1
            })

        if progress >= 1:
            del self.to_go[0]

        return 1 if self.useMeters else MS_PER_FRAME
    
    def addToGo(self, dst_point: Point):
        """
        Extends the current by a set of points ending at dst_point.
        """
        src_point = self.path[-1]

        path = util.find_path_between_points_in_osrm(src_point.toTuple(), dst_point.toTuple()) + [dst_point.toTuple()]
        self.to_go += [Point(*p) for p in path[1:]]

    def finishTrip(self):
        self.active = False
        self.events.append({
            "type": "FINISH"
        })

class Terminal:
    def __init__(
            self,
            location: Point,
            capacity: int
    ):
        self.location = location
        self.capacity = capacity
        
        self.queue = []
        self.passengers = []
    
    def isEmptyOfPassengers(self):
        return len(self.passengers) == 0

    def isEmptyOfTrikes(self):
        return len(self.queue) == 0

    def addTricycle(
            self,
            tricycle: Tricycle
    ):
        self.queue.append(tricycle)
        tricycle.active = False
    
    def addPassenger(
            self,
            passenger: Passenger
    ):
        self.passengers.append(passenger)
    
    def loadTricycle(self):
        "Tries to load passenger to the top tricycle"

        # only process if there are both passengers and trikes
        if len(self.queue) == 0 or len(self.passengers) == 0:
            return None
        
        res = {
            "tricycle": None,
            "passengers": [],
            "wait": 0
        }

        waitTime = 0
        topTrike = self.queue[0]
        while len(self.passengers) > 0:
            topPassenger = self.passengers[0]
            if topTrike.loadPassenger(topPassenger):
                self.passengers = self.passengers[1:]
                res["passengers"].append(topPassenger)
                waitTime += 0
            else:
                break
        if res["passengers"]:
            res["tricycle"] = topTrike
            res["wait"] = waitTime
        
        return res
    
    def popTricycle(self):
        if not self.isEmptyOfTrikes():
            trike = self.queue[0]
            self.queue = self.queue[1:]
            trike.active = True
            return trike