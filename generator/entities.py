import json
import util
from enum import Enum

MS_PER_FRAME = 1000

# PICKUP / DROPOFF PARAMETERS
DETECTION_RADIUS_METERS = 50  # Larger radius for detection
DROPOFF_RADIUS_METERS = 2  # Smaller radius for actual dropoff
PICKUP_RADIUS_METERS = 2  # Smaller radius for actual pickup

class PassengerStatus(Enum):
    WAITING = 0
    ENQUEUED = 1
    ONBOARD = 2
    COMPLETED = 3

class TricycleStatus(Enum):
    IDLE = 0          # Available for new assignments
    SERVING = 1       # Currently serving passengers
    TERMINAL = 2      # Parked at a terminal
    ROAMING = 3       # Actively roaming (for roaming tricycles)
    RETURNING_TO_TERMINAL = 4  # Returning to a terminal after dropping off passengers

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
    """
    Represents the simulation area and manages spatial queries for entities.
    Supports proximity-based operations and efficient spatial lookups.
    """
    def __init__(
            self,
            x_min: float,
            y_min: float,
            x_max: float,
            y_max: float
    ):
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        
        # Store all passengers in a flat list for now
        # TODO: Consider implementing spatial indexing (e.g., R-tree) for better performance
        self.passengers = []
    
    def addPassenger(self, passenger: 'Passenger'):
        """
        Adds a passenger to the map.
        
        Args:
            passenger: The full Passenger object to add. This includes all passenger
                      information including source, destination, status, and events.
                      The map stores the complete object to support operations like
                      proximity detection, status updates, and event tracking.
        """
        self.passengers.append(passenger)
    
    def removePassenger(self, passenger: 'Passenger'):
        """
        Removes a passenger from the map.
        """
        self.passengers = list(filter(lambda x: x != passenger, self.passengers))
    
    def getNearbyPassengers(self, point: Point, radiusMeters: float) -> list['Passenger']:
        """
        Returns all passengers within the specified radius of the given point.
        Uses haversine distance for accurate distance calculation.
        """
        nearby = []
        for passenger in self.passengers:
            distance = util.haversine(*point.toTuple(), *passenger.src.toTuple())
            if distance <= radiusMeters:
                nearby.append(passenger)
        return nearby
    
    def isAtLocation(self, point1: Point, point2: Point, thresholdMeters: float = 2.0) -> bool:
        """
        Checks if two points are within the specified threshold distance of each other.
        Uses haversine distance for accurate distance calculation.
        """
        distance = util.haversine(*point1.toTuple(), *point2.toTuple())
        return distance <= thresholdMeters
    
    def getBounds(self) -> tuple[float, float, float, float]:
        """
        Returns the map boundaries as (x_min, y_min, x_max, y_max).
        """
        return (self.x_min, self.y_min, self.x_max, self.y_max)
    
    def isWithinBounds(self, point: Point) -> bool:
        """
        Checks if a point is within the map boundaries.
        """
        return (self.x_min <= point.x <= self.x_max and 
                self.y_min <= point.y <= self.y_max)

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

class Passenger(Actor):
    """
    Represents a passenger in the simulation.
    Handles its own state transitions and event recording.
    """
    def __init__(
            self, 
            id,
            src: Point, 
            dest: Point,
            createTime: int,
            deathTime: int,
            status: PassengerStatus = PassengerStatus.WAITING
    ):
        """
        Initialize a new passenger with source and destination points.
        Records the APPEAR event at creation time.
        """
        super().__init__(createTime, deathTime)
        self.id = id
        self.src = src
        self.dest = dest
        self.status = status
        self.pickupTime = -1  # Time when passenger is picked up
        self.claimed_by = None  # Track which tricycle has claimed this passenger

        self.path.append(self.src)
        
        # Record the APPEAR event
        self.events.append({
            "type": "APPEAR",
            "time": createTime,
            "location": [self.src.x, self.src.y]
        })

    ########## State Management Methods ##########

    def onEnqueue(self, trike_id: str, time: int, location: list[float]):
        """
        Updates passenger status when claimed by a tricycle.
        Called when a tricycle detects the passenger and claims them for pickup.
        """
        self.status = PassengerStatus.ENQUEUED
        self.claimed_by = trike_id
        # Record the ENQUEUE event
        self.events.append({
            "type": "ENQUEUE",
            "data": trike_id,
            "time": time,
            "location": location
        })
    
    def onLoad(self, trike_id: str, time: int, location: list[float]):
        """
        Records the LOAD event and updates passenger status when loaded into a tricycle.
        Called when a tricycle successfully picks up the passenger.
        """
        self.events.append({
            "type": "LOAD",
            "data": trike_id,
            "time": time,
            "location": location
        })
        self.status = PassengerStatus.ONBOARD
        self.pickupTime = time
        self.claimed_by = trike_id  # Set claimed_by when passenger is loaded
    
    def onDropoff(self, time: int, location: list[float]):
        """
        Records the DROP-OFF event and updates passenger status when dropped off.
        Also records the death time for metrics.
        Called when a tricycle successfully delivers the passenger to their destination.
        """
        self.events.append({
            "type": "DROP-OFF",
            "data": self.claimed_by,  # Add tricycle ID that dropped off the passenger
            "time": time,
            "location": location
        })
        self.status = PassengerStatus.COMPLETED
        self.deathTime = time  # Use deathTime to record dropoff time
    
    def onReset(self, time: int, location: list[float]):
        """
        Resets passenger status back to WAITING and clears any claims.
        Called when a tricycle fails to load an enqueued passenger (e.g., capacity reached).
        """
        self.status = PassengerStatus.WAITING
        # Store the tricycle ID before clearing the claim
        trike_id = self.claimed_by
        self.claimed_by = None
        # Record the RESET event with the tricycle ID
        self.events.append({
            "type": "RESET",
            "data": trike_id,  # Add tricycle ID that reset the passenger
            "time": time,
            "location": location
        })

    ########## Serialization Methods ##########

    def toJSON(self):
        """
        Converts the passenger's state to a JSON-compatible dictionary.
        Used for serialization and visualization.
        """
        return {
            "id": self.id,
            "type": "passenger",
            "src": self.src.toJSON(),
            "dst": self.dest.toJSON(),
            "createTime": self.createTime,
            "deathTime": self.deathTime,
            "pickupTime": self.pickupTime,
            "path": [p.toJSON() for p in self.path],
            "events": self.events,  # Add events to JSON output
            "claimed_by": self.claimed_by
        }

    def __str__(self):
        """Returns a string representation of the passenger's journey."""
        return f'P[{self.src} to {self.dest}]'

    def __repr__(self) -> str:
        """Returns a JSON string representation of the passenger."""
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
        self.status = TricycleStatus.ROAMING if isRoaming else TricycleStatus.IDLE

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

        # assumes all trikes are created at the same time = 0
        # if not, time must be passed as a parameter at initialization
        self.events.append({
            "type": "APPEAR",
            "time": 0,
            "location": [self.x, self.y]
        })

    ########## Movement and Navigation Methods ##########

    def curPoint(self) -> Point:
        """
        Returns the current position of the tricycle.
        """
        return self.path[-1]
    
    def loadNextCyclePoint(self):
        """
        Adds the next point in the cycle to the to-go list.
        Used by roaming tricycles to continue their cycle path.
        """
        curPoint = self.path[-1]
        nxtPoint = self.roamPath.getNextPoint(curPoint)
        self.addToGo(nxtPoint)

    def moveTrike(self, current_time: int):
        """
        Moves the tricycle towards the next point in the to_go queue.
        If the next point is too far to reach immediately, the tricycle will only move as far as possible.
        Only moves if the tricycle is not in TERMINAL status.
        Returns the time taken in moving.
        """
        
        if self.status == TricycleStatus.TERMINAL:
            print(f"Tricycle {self.id} cannot move while in TERMINAL status", flush=True)
            return 0

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
                "data": 1,
                "time": current_time,
                "location": [self.path[-1].x, self.path[-1].y]
            })

        if progress >= 1:
            del self.to_go[0]

        return 1 if self.useMeters else MS_PER_FRAME
    
    def addToGo(self, dst_point: Point):
        """
        Extends the current route by adding a path to the destination point.
        Uses OSRM to find a valid route between current position and destination.
        """
        src_point = self.path[-1]

        path = util.find_path_between_points_in_osrm(src_point.toTuple(), dst_point.toTuple()) + [dst_point.toTuple()]
        self.to_go += [Point(*p) for p in path[1:]]

    ########## Passenger Management Methods ##########

    def hasPassenger(self):
        """
        Returns True if the tricycle has any passengers.
        """
        return len(self.passengers) > 0
    
    def loadPassenger(self, p: Passenger, current_time: int):
        """
        Attempts to load a passenger into the tricycle.
        Returns True if successful, False if tricycle is at capacity.
        """
        if len(self.passengers) >= self.capacity:
            return False
        self.events.append({
            "type": "LOAD",
            "data": p.id,
            "time": current_time,
            "location": [self.path[-1].x, self.path[-1].y]
        })
        self.events.append({
            "type": "WAIT",
            "data": 500,
            "time": current_time,
            "location": [self.path[-1].x, self.path[-1].y]
        })
        self.passengers.append(p)
        p.onLoad(self.id, current_time, [self.path[-1].x, self.path[-1].y])
        self.setStatus(TricycleStatus.SERVING)
        return True

    def enqueueNearbyPassengers(self, current_time: int):
        """
        Detects passengers within detection radius and adds their pickup points to to_go.
        Only considers passengers that are WAITING and if the tricycle has capacity.
        Updates passenger status to ENQUEUED when added to a tricycle's route.
        Returns list of detected passengers for tracking.
        """
        if not self.map:
            raise Exception("Not backward compatible. Please use a map")
        
        cur = self.path[-1]
        
        # Skip if tricycle is at capacity
        if len(self.passengers) >= self.capacity:
            return []
        
        # Get nearby passengers using the new Map method
        nearby_passengers = self.map.getNearbyPassengers(cur, DETECTION_RADIUS_METERS)
        
        enqueued_passengers = []
        for p in nearby_passengers:
            # Only consider waiting passengers
            if p.status != PassengerStatus.WAITING:
                continue
                
            # Update passenger status to ENQUEUED and claim them
            p.onEnqueue(self.id, current_time, [p.src.x, p.src.y])  # Use passenger source location
            enqueued_passengers.append(p)
            # Add pickup point to the front of to_go if not already there
            if not any(point.x == p.src.x and point.y == p.src.y for point in self.to_go):
                # Get the path to the pickup point
                try:
                    path_to_pickup = util.find_path_between_points_in_osrm(cur.toTuple(), p.src.toTuple())
                    # Add the path points to the front of to_go
                    self.to_go = [Point(*point) for point in path_to_pickup[1:]] + self.to_go
                    print(f"Added pickup point for {p.id} to the front of {self.id}'s route", flush=True)
                except util.NoRoute:
                    print(f"No route to pickup point for {p.id}, skipping", flush=True)
        
        return enqueued_passengers

    def tryLoad(self, current_time: int):
        """
        Attempts to load passengers within a certain pickup radius of the tricycle's current location.
        Only loads passengers that are ENQUEUED and were claimed by this tricycle.
        Uses haversine distance for realistic distance calculation.
        NOTE: This should only load ROAD passengers (i.e. not within a terminal). Passengers within a terminal are handled by the terminal.
        """
        if not self.map:
            raise Exception("Not backward compatible. Please use a map")
        
        cur = self.path[-1]
        
        # Get nearby passengers using the new Map method
        nearby_passengers = self.map.getNearbyPassengers(cur, PICKUP_RADIUS_METERS)
        
        loaded = []
        for p in nearby_passengers:
            # Only consider ENQUEUED passengers claimed by this tricycle
            if p.status != PassengerStatus.ENQUEUED or p.claimed_by != self.id:
                continue
                
            if self.loadPassenger(p, current_time):
                loaded.append(p)
                self.map.removePassenger(p)
                print(f"Loaded {p.id} into {self.id}", flush=True)
            else:
                # If we can't load the passenger (e.g., capacity reached),
                # reset their status back to WAITING and clear claim
                p.onReset(current_time, [p.src.x, p.src.y])  # Use passenger source location
                print(f"Could not load {p.id} into {self.id}, resetting status to WAITING", flush=True)
        
        return loaded

    def tryOffload(self, current_time: int):
        """
        Attempts to drop passengers within a certain radius of their destination.
        Uses haversine distance for realistic distance calculation.
        Returns a list of passengers that were dropped off.
        """
        if not self.map:
            raise Exception("Not backward compatible. Please use a map")
        
        cur = self.path[-1]
        dropped = False

        # Check if any passengers destinations are within DROPOFF_RADIUS_METERS
        for index, p in enumerate(self.passengers[:]):
            # Calculate distance using haversine (in meters)
            distance = util.haversine(*cur.toTuple(), *p.dest.toTuple())
            if distance <= DROPOFF_RADIUS_METERS:
                dropped = True
                self.events.append({
                    "type": "DROP-OFF",
                    "data": p.id, 
                    "time": current_time,
                    "location": [cur.x, cur.y]
                })
                self.passengers = list(filter(lambda x : x.id != p.id, self.passengers))
                p.onDropoff(current_time, [cur.x, cur.y])
                print("dropped", p.id, "at distance", distance, "meters", flush=True)
                yield p
        
        # If all passengers are dropped off, update status
        if not self.passengers:
            if self.isRoaming:
                self.setStatus(TricycleStatus.ROAMING)
            elif self.status != TricycleStatus.RETURNING_TO_TERMINAL:  # Only set if not already returning
                self.setStatus(TricycleStatus.RETURNING_TO_TERMINAL)
                print(f"Tricycle {self.id} is returning to terminal after dropping off all passengers", flush=True)
        
        # If a passenger was dropped off, wait for 500ms before processing the next passenger
        if dropped:
            self.events.append({
                "type": "WAIT",
                "data": 500,
                "time": current_time,
                "location": [self.path[-1].x, self.path[-1].y]
            })

    def scheduleNextPassenger(self):
        """
        Schedules the next passenger to offload by OVERLOADING the current route
        and WITHOUT removing the passenger from the passenger queue. These are important
        since it may be possible to take in a new passenger that should be prioritized.

        Returns the next passenger to offload, or None if there are no passengers to offload.
        """
        if len(self.passengers) == 0:
            raise NoMorePassengers
        
        # If no scheduler, just offload the first passenger
        if self.scheduler is None:
            print("no scheduler", flush=True)
            p = self.passengers[0]
        else:
            # Get the next passenger to offload from the scheduler
            index, p = self.scheduler(self.path[-1], self.passengers)
            # self.passengers.pop(index)

        # Get the path to the passenger's destination
        src_point = self.path[-1]
        dst_point = p.dest
        try:
            path_to_passenger_raw = util.find_path_between_points_in_osrm(src_point.toTuple(), dst_point.toTuple()) + [dst_point.toTuple()]
        except util.NoRoute:
            print(f"No Route. Ignoring {p.id} going to {dst_point.toTuple()}")
            return None

        # A valid path must have at least 3 points:
        # 1. Start point (current location)
        # 2. At least one intermediate point (to follow road network)
        # 3. End point (passenger destination)
        # If we have fewer points, the tricycle doesn't need to move
        if len(path_to_passenger_raw) < 3:
            print(f"Path too short for {p.id} (length={len(path_to_passenger_raw)}), skipping", flush=True)
            return None
        
        # Create a new path object
        path_to_passenger = Path(*path_to_passenger_raw)

        # Add the path to the to_go queue
        self.to_go = [Point(*p) for p in path_to_passenger_raw[1:]]

        return p

    def finishTrip(self, current_time: int):
        """
        Marks the tricycle as inactive and records the finish event.
        Called when the tricycle completes its route or encounters an error.
        """
        self.active = False
        self.events.append({
            "type": "FINISH", 
            "time": current_time,
            "location": [self.path[-1].x, self.path[-1].y]
        })

    def validateStatusTransition(self, new_status: TricycleStatus) -> bool:
        """Validate if the status transition is allowed."""
        valid_transitions = {
            TricycleStatus.IDLE: [TricycleStatus.SERVING, TricycleStatus.TERMINAL],
            TricycleStatus.SERVING: [TricycleStatus.RETURNING_TO_TERMINAL, TricycleStatus.ROAMING],
            TricycleStatus.TERMINAL: [TricycleStatus.SERVING],
            TricycleStatus.ROAMING: [TricycleStatus.SERVING],
            TricycleStatus.RETURNING_TO_TERMINAL: [TricycleStatus.TERMINAL]
        }
        return new_status in valid_transitions.get(self.status, [])

    def setStatus(self, new_status: TricycleStatus) -> bool:
        """
        Safely changes the tricycle's status if the transition is valid.
        Returns True if the transition was successful, False otherwise.
        """
        if self.validateStatusTransition(new_status):
            self.status = new_status
            return True
        print(f"Invalid status transition for {self.id}: {self.status} -> {new_status}", flush=True)
        return False

    ########## Serialization Methods ##########

    def toJSON(self):
        """
        Converts the tricycle's state to a JSON-compatible dictionary.
        Used for serialization and visualization.
        """
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
        """
        Returns a JSON string representation of the tricycle.
        Used for debugging and logging.
        """
        return json.dumps(self.toJSON())

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

    def addTricycle(self, tricycle: Tricycle):
        """Add a tricycle to the terminal if it's in a valid state."""
        if tricycle.status not in [TricycleStatus.IDLE, TricycleStatus.RETURNING_TO_TERMINAL]:
            print(f"Cannot add tricycle {tricycle.id} to terminal: invalid status {tricycle.status}", flush=True)
            return
        self.queue.append(tricycle)
        tricycle.active = False
        if not tricycle.setStatus(TricycleStatus.TERMINAL):
            print(f"Warning: Failed to set tricycle {tricycle.id} to TERMINAL status", flush=True)
    
    def addPassenger(
            self,
            passenger: Passenger
    ):
        self.passengers.append(passenger)
    
    def loadTricycle(self, current_time: int):
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
            if topTrike.loadPassenger(topPassenger, current_time):
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