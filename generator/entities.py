import json
import util
from scenarios.util import gen_random_bnf_roam_path
from enum import Enum

MS_PER_FRAME = 1000

# PICKUP / DROPOFF PARAMETERS
DETECTION_RADIUS_METERS = 200  # Increased radius for detection
DROPOFF_RADIUS_METERS = 20  # Increased radius for actual dropoff
PICKUP_RADIUS_METERS = 20  # Increased radius for actual pickup

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
    RETURNING = 4     # Returning to terminal/roam path after dropping off passengers
    ENQUEUING = 5     # Proceeding to pick up an enqueued passenger

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
        self.tricycles = []  # Track all tricycles in the map
    
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

    def addTricycle(self, tricycle: 'Tricycle'):
        """
        Adds a tricycle to the map.
        
        Args:
            tricycle: The Tricycle object to add
        """
        self.tricycles.append(tricycle)

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
    Represents a tricycle in the simulation with the following capabilities:
    1. Roaming - can run continuously without fixed start/end points
    2. Point-to-Point - can run between specific locations
    3. Multi-passenger - can pick up and drop off multiple passengers
    4. Path Management - maintains and updates routes using OSRM
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
            useMeters: bool = False,
            maxCycles: int = 5
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
        self.cycleCount = 0 # To count how many cycles a tricycle has roamed with no pickups
        self.maxCycles = maxCycles # To count how many cycles a tricycle can roam with no pickups before it is considered dead

        # initialize the tricycle
        self.isRoaming = isRoaming
        self.x = startX
        self.y = startY
        self.passengers = []
        self.enqueuedPassenger = None  # Track single enqueued passenger
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

    ########## Core Movement Methods ##########

    def curPoint(self) -> Point:
        """Returns the current position of the tricycle."""
        return self.path[-1]

    def moveTrike(self, current_time: int):
        """
        Moves the tricycle towards the next point in the to_go queue.
        
        Args:
            current_time: Current simulation time
            
        Returns:
            int: Time taken for the movement (1 for meters, MS_PER_FRAME for frames)
            
        Note:
            - Only moves if not in TERMINAL status
            - Updates metrics for distance traveled
            - Records movement events
        """
        
        if self.status == TricycleStatus.TERMINAL:
            print(f"Tricycle {self.id} cannot move while in TERMINAL status", flush=True)
            return 0

        if not self.map:
            raise Exception("Not backward compatible. Please use a map")
        
        cur = self.path[-1]
        
        # move to next position
        if not self.to_go:
            print(f"Tricycle {self.id} has no points in to_go queue", flush=True)
            return 0
        
        nxt = self.to_go[0]
        print(f"Tricycle {self.id} attempting to move from {cur.toTuple()} to {nxt.toTuple()}", flush=True)

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
            print(f"Tricycle {self.id} reached point {nxt.toTuple()}, removing from to_go", flush=True)
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
            print(f"Tricycle {self.id} completed move to {nxt.toTuple()}, removing from to_go", flush=True)
            del self.to_go[0]

        return 1 if self.useMeters else MS_PER_FRAME
    
    ########## Path Management Methods ##########

    def updatePath(self, new_destination: Point, priority: str = 'append'):
        """
        Updates the tricycle's path with a new destination.
        
        Args:
            new_destination: The target point to navigate to
            priority: How to integrate the new path
                - 'front': Add to front of queue (for passenger pickups)
                - 'replace': Replace entire path (for passenger destinations)
                - 'append': Append to end (for roaming)
                
        Returns:
            bool: True if path was successfully updated, False otherwise
            
        Note:
            - Validates path length and duplicates
            - Uses OSRM for route finding
            - Handles path priority based on context
            - Ensures path continuity when adding new paths
        """
        # Only block path updates if we're enqueuing AND this isn't for the enqueued passenger
        if self.status == TricycleStatus.ENQUEUING:
            if not self.enqueuedPassenger or not self.map.isAtLocation(new_destination, self.enqueuedPassenger.src):
                print(f"Tricycle {self.id} cannot update path while enqueuing", flush=True)
                return False
        
        try:
            print(f"Tricycle {self.id} finding path from {self.path[-1].toTuple()} to {new_destination.toTuple()} with priority {priority}", flush=True)
            
            # If we're already at the destination, no need to find a path
            if self.map.isAtLocation(self.path[-1], new_destination):
                print(f"Tricycle {self.id} already at destination {new_destination.toTuple()}", flush=True)
                return True
                
            # Find path to destination
            path = util.find_path_between_points_in_osrm(
                self.path[-1].toTuple(), 
                new_destination.toTuple()
            )
            
            # Validate path
            if not path:
                print(f"No path found from {self.path[-1].toTuple()} to {new_destination.toTuple()}", flush=True)
                return False
                
            if len(path) < 2:
                print(f"Path too short from {self.path[-1].toTuple()} to {new_destination.toTuple()}, got {len(path)} points", flush=True)
                return False
            
            print(f"Tricycle {self.id} found path with {len(path)} points", flush=True)
            
            # Check for duplicate destinations
            if self.to_go and self.to_go[-1].toTuple() == new_destination.toTuple():
                print(f"Already en route to {new_destination.toTuple()}", flush=True)
                return True
            
            # Convert to Points
            new_points = [Point(*p) for p in path]
            
            if priority == 'replace':
                # When replacing path, clear current path and add new one
                print(f"Tricycle {self.id} replacing path with {len(new_points)} points", flush=True)
                self.to_go = new_points
            elif priority == 'front':
                # When adding to front, we need to ensure the paths connect
                if self.to_go:
                    # First find path from current position to new destination
                    print(f"Tricycle {self.id} finding path from current position {self.path[-1].toTuple()} to {new_destination.toTuple()}", flush=True)
                    path_to_dest = util.find_path_between_points_in_osrm(
                        self.path[-1].toTuple(),
                        new_destination.toTuple()
                    )
                    if len(path_to_dest) >= 2:
                        # Then find path from new destination to first point in current path
                        print(f"Tricycle {self.id} finding connecting path from {new_destination.toTuple()} to {self.to_go[0].toTuple()}", flush=True)
                        connecting_path = util.find_path_between_points_in_osrm(
                            new_destination.toTuple(),
                            self.to_go[0].toTuple()
                        )
                        if len(connecting_path) >= 2:
                            # Add new path + connecting path + rest of current path
                            path_to_dest_points = [Point(*p) for p in path_to_dest]
                            connecting_points = [Point(*p) for p in connecting_path]
                            
                            # Remove any duplicate points at the start
                            if path_to_dest_points and self.path[-1].toTuple() == path_to_dest_points[0].toTuple():
                                path_to_dest_points = path_to_dest_points[1:]
                            
                            self.to_go = path_to_dest_points + connecting_points + self.to_go[1:]
                            print(f"Tricycle {self.id} added {len(path_to_dest_points)} points to front with {len(connecting_points)} connecting points", flush=True)
                        else:
                            print(f"Could not find connecting path from {new_destination.toTuple()} to {self.to_go[0].toTuple()}", flush=True)
                            return False
                    else:
                        print(f"Could not find path from current position to {new_destination.toTuple()}", flush=True)
                        return False
                else:
                    # If no current path, just add new path
                    print(f"Tricycle {self.id} adding {len(new_points)} points to empty path", flush=True)
                    self.to_go = new_points
            else:  # append
                # When appending, we need to ensure the paths connect
                if self.to_go:
                    # Find path from last point in current path to new destination
                    print(f"Tricycle {self.id} finding connecting path from {self.to_go[-1].toTuple()} to {new_destination.toTuple()}", flush=True)
                    connecting_path = util.find_path_between_points_in_osrm(
                        self.to_go[-1].toTuple(),
                        new_destination.toTuple()
                    )
                    if len(connecting_path) >= 2:
                        # Add connecting path to new destination
                        connecting_points = [Point(*p) for p in connecting_path]
                        self.to_go = self.to_go[:-1] + connecting_points
                        print(f"Tricycle {self.id} added {len(connecting_points)} connecting points to path", flush=True)
                    else:
                        print(f"Could not find connecting path from {self.to_go[-1].toTuple()} to {new_destination.toTuple()}", flush=True)
                        return False
                else:
                    # If no current path, just add new path
                    print(f"Tricycle {self.id} adding {len(new_points)} points to empty path", flush=True)
                    self.to_go = new_points
            
            return True
            
        except util.NoRoute:
            print(f"No route found from {self.path[-1].toTuple()} to {new_destination.toTuple()}", flush=True)
            return False

    def loadNextCyclePoint(self):
        """
        Adds the next point in the cycle to the to-go list.
        Used by roaming tricycles to continue their cycle path.
        
        Note:
            - Only applicable for roaming tricycles
            - Appends next point to existing path
        """
        if not self.roamPath:
            return
        
        curPoint = self.path[-1]
        nxtPoint = self.roamPath.getNextPoint(curPoint)
        
        if not self.updatePath(nxtPoint, priority='append'):
            print(f"Failed to add next cycle point", flush=True)

    def newRoamPath(self, current_time: int):
        """
        Generates a new roaming path for the tricycle.
        Uses updatePath with append priority to ensure path continuity
        and not interrupt current passenger service.
        """
        # Consider including probabilities for different path types
        new_path = gen_random_bnf_roam_path()
        if new_path:
            # Use 'append' priority to maintain path continuity and current service
            if self.updatePath(new_path.getStartPoint(), priority='append'):
                self.roamPath = new_path
                self.cycleCount = 0
                
                # Add event recording the new roam path endpoints
                self.events.append({
                    "type": "NEW_ROAM_PATH",
                    "data": {
                        "start": new_path.getStartPoint().toTuple(),
                        "end": new_path.path[-1].toTuple()
                    },
                    "time": current_time,
                    "location": [self.path[-1].x, self.path[-1].y]
                })
                return [new_path.getStartPoint(), new_path.path[-1]]
            else:
                print(f"Failed to update path for new roam path", flush=True)
                return None

    ########## Passenger Management Methods ##########

    def hasPassenger(self):
        """Returns True if the tricycle has any passengers."""
        return len(self.passengers) > 0

    def enqueueNearbyPassenger(self, current_time: int):
        """
        Enqueues the closest nearby waiting passenger.
        
        Args:
            current_time: Current simulation time
            
        Returns:
            Passenger | None: The enqueued passenger if one was found and enqueued, None otherwise
            
        Note:
            - Only considers WAITING passengers
            - Only enqueues one passenger at a time (closest one)
            - Adds pickup point to front of path
        """
        if not self.map:
            raise Exception("Not backward compatible. Please use a map")
        
        # If we already have an enqueued passenger, don't try to enqueue another one
        if self.enqueuedPassenger is not None:
            print(f"Tricycle {self.id} already has enqueued passenger {self.enqueuedPassenger}", flush=True)
            return None
        
        cur = self.path[-1]
        
        # Calculate how many more passengers we can take (considering both loaded and enqueued)
        remaining_capacity = self.capacity - (len(self.passengers) + 1)
        if remaining_capacity <= 0:
            return None
        
        # Get nearby passengers using the new Map method
        nearby_passengers = self.map.getNearbyPassengers(cur, DETECTION_RADIUS_METERS)
        
        # Sort passengers by distance
        passenger_distances = []
        for p in nearby_passengers:
            if p.status == PassengerStatus.WAITING:
                distance = util.haversine(*cur.toTuple(), *p.src.toTuple())
                passenger_distances.append((distance, p))
        
        # Sort by distance
        passenger_distances.sort(key=lambda x: x[0])
        
        # Only take the closest passenger
        if passenger_distances:
            distance, p = passenger_distances[0]
            
            # Update passenger status to ENQUEUED and claim them
            p.onEnqueue(self.id, current_time, [p.src.x, p.src.y])
            self.enqueuedPassenger = p  # Track enqueued passenger
            self.events.append({
                "type": "ENQUEUE",
                "data": p.id,
                "time": current_time,
                "location": [p.src.x, p.src.y]
            })

            # Set status to ENQUEUING
            self.updateStatus(TricycleStatus.ENQUEUING)

            # Add pickup point to the front of to_go if not already there
            if not any(point.x == p.src.x and point.y == p.src.y for point in self.to_go):
                if not self.updatePath(p.src, priority='front'):
                    print(f"Failed to add pickup point for {p.id}", flush=True)
                    # If we failed to add the pickup point, reset the passenger
                    p.onReset(current_time, [p.src.x, p.src.y])
                    self.enqueuedPassenger = None
                    # Reset status based on roaming state
                    if self.isRoaming:
                        self.updateStatus(TricycleStatus.ROAMING)
                    else:
                        self.updateStatus(TricycleStatus.IDLE)
                else:
                    print(f"Enqueued passenger {p.id} at distance {distance:.2f}m", flush=True)
                    return p
        
        return None

    def loadPassenger(self, p: Passenger, current_time: int):
        """
        Attempts to load a passenger into the tricycle.
        
        Args:
            p: The passenger to load
            current_time: Current simulation time
            
        Returns:
            bool: True if successful, False if at capacity
            
        Note:
            - Records loading events
            - Updates passenger status
            - Changes tricycle status to SERVING if not already serving
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
            "data": 100,
            "time": current_time,
            "location": [self.path[-1].x, self.path[-1].y]
        })

        self.passengers.append(p)
        self.enqueuedPassenger = None  # Clear enqueued passenger
        p.onLoad(self.id, current_time, [self.path[-1].x, self.path[-1].y])
        
        # Reset cycle count on successful pickup
        self.cycleCount = 0
        
        # Only set status to SERVING if not already serving
        if self.status != TricycleStatus.SERVING:
            self.updateStatus(TricycleStatus.SERVING)
        return True

    def tryLoad(self, current_time: int):
        """
        Attempts to load enqueued passengers at their exact spawn location.
        
        Args:
            current_time: Current simulation time
            
        Returns:
            list[Passenger]: List of successfully loaded passengers
            
        Note:
            - Only loads ENQUEUED passengers claimed by this tricycle
            - Resets passengers if loading fails
            - Uses exact location matching for pickup
            - Schedules next passenger's destination after successful load
        """
        if not self.map:
            raise Exception("Not backward compatible. Please use a map")
        
        cur = self.path[-1]
        
        # Get nearby passengers using the new Map method
        nearby_passengers = self.map.getNearbyPassengers(cur, DETECTION_RADIUS_METERS)
        
        loaded = []
        for p in nearby_passengers:
            # Only consider ENQUEUED passengers claimed by this tricycle
            if p.status != PassengerStatus.ENQUEUED:
                print(f"Passenger {p.id} not in ENQUEUED status (current: {p.status})", flush=True)
                continue
            if p.claimed_by != self.id:
                print(f"Passenger {p.id} claimed by {p.claimed_by}, not {self.id}", flush=True)
                continue
                
            # Check if we're exactly at the passenger's spawn location
            if self.map.isAtLocation(cur, p.src):
                if len(self.passengers) >= self.capacity:
                    print(f"Tricycle {self.id} at capacity ({len(self.passengers)}/{self.capacity})", flush=True)
                    # If we can't load the passenger (e.g., capacity reached),
                    # reset their status back to WAITING and clear claim
                    print(f"Could not load {p.id} into {self.id}, resetting status to WAITING", flush=True)
                    p.onReset(current_time, [p.src.x, p.src.y])
                    continue

                if self.loadPassenger(p, current_time):
                    loaded.append(p)
                    self.map.removePassenger(p)
                    print(f"Loaded {p.id} into {self.id} at exact spawn location", flush=True)
                    
                    # Add a small wait after loading to ensure stability
                    self.events.append({
                        "type": "WAIT",
                        "data": 200,  # 200ms wait
                        "time": current_time,
                        "location": [self.path[-1].x, self.path[-1].y]
                    })
                    
                    # After loading a passenger, schedule their destination
                    try:
                        if self.scheduleNextPassenger():
                            print(f"Scheduled destination for {p.id}", flush=True)
                    except NoMorePassengers:
                        print(f"No more passengers to schedule for {self.id}", flush=True)
                    self.updateStatus(TricycleStatus.SERVING)
                else:
                    # If we can't load the passenger (e.g., capacity reached),
                    # reset their status back to WAITING and clear claim
                    print(f"Could not load {p.id} into {self.id}, resetting status to WAITING", flush=True)
                    p.onReset(current_time, [p.src.x, p.src.y])
            else:
                print(f"Tricycle {self.id} is not at {p.id}'s exact spawn location", flush=True)
        
        return loaded

    def tryOffload(self, current_time: int):
        """
        Attempts to drop off passengers at their destinations.
        
        Args:
            current_time: Current simulation time
            
        Returns:
            list[Passenger]: List of passengers that were successfully dropped off
            
        Note:
            - Uses haversine distance for realistic dropoff
            - Updates tricycle status after all passengers are dropped
            - Adds wait time after dropoff
        """
        if not self.map:
            raise Exception("Not backward compatible. Please use a map")
        
        cur = self.path[-1]
        dropped = []
        dropped_any = False

        # Check if any passengers destinations are within DROPOFF_RADIUS_METERS
        for index, p in enumerate(self.passengers[:]):
            # Calculate distance using haversine (in meters)
            distance = util.haversine(*cur.toTuple(), *p.dest.toTuple())
            print(f"Tricycle {self.id} is {distance:.2f}m away from {p.id}'s destination at {p.dest.toTuple()}", flush=True)
            if distance <= DROPOFF_RADIUS_METERS:
                dropped_any = True
                self.events.append({
                    "type": "DROP-OFF",
                    "data": p.id, 
                    "time": current_time,
                    "location": [cur.x, cur.y]
                })
                self.passengers = list(filter(lambda x : x.id != p.id, self.passengers))
                p.onDropoff(current_time, [cur.x, cur.y])
                dropped.append(p)
                print(f"Dropped {p.id} at distance {distance:.2f}m", flush=True)
            else:
                print(f"Tricycle {self.id} is too far ({distance:.2f}m) from {p.id}'s destination to drop off", flush=True)
        
        # If all passengers are dropped off, update status
        if not self.passengers:
            if self.isRoaming:
                if self.status != TricycleStatus.ROAMING:
                    self.updateStatus(TricycleStatus.ROAMING)
            elif self.status != TricycleStatus.RETURNING:
                self.updateStatus(TricycleStatus.RETURNING)
        
        # Add a small wait after dropping off passengers to prevent erratic movement
        if dropped_any:
            self.events.append({
                "type": "WAIT",
                "data": 100,  # Reduced wait time to 100ms
                "time": current_time,
                "location": [self.path[-1].x, self.path[-1].y]
            })
            
            # Schedule next passenger if we still have passengers
            if self.passengers:
                try:
                    if self.scheduleNextPassenger():
                        print(f"Scheduled next passenger after dropoff for {self.id}", flush=True)
                except NoMorePassengers:
                    print(f"No more passengers to schedule for {self.id}", flush=True)
        
        return dropped

    def scheduleNextPassenger(self):
        """
        Schedules the next passenger to drop off.
        
        Returns:
            Passenger: Next passenger to drop off, or None if no valid path
            
        Note:
            - Uses scheduler if available
            - Adds path to front of queue (for passenger destinations)
            - Maintains passenger queue for potential new pickups
        """
        
        # If no scheduler, just offload the first passenger
        if self.scheduler is None:
            p = self.passengers[0]
        else:
            # Get the next passenger to offload from the scheduler
            index, p = self.scheduler(self.path[-1], self.passengers)

        # Get the path to the passenger's destination
        src_point = self.path[-1]
        dst_point = p.dest
        print(f"Tricycle {self.id} attempting to schedule path to {p.id}'s destination at {dst_point.toTuple()}", flush=True)
        try:
            # Use 'front' priority instead of 'replace' to maintain path continuity
            if not self.updatePath(p.dest, priority='front'):
                print(f"Failed to update path for {p.id} to {dst_point.toTuple()}", flush=True)
                return None
            print(f"Successfully scheduled path for {p.id} to {dst_point.toTuple()}", flush=True)
            self.updateStatus(TricycleStatus.SERVING)
            return p
        
        except util.NoRoute:
            print(f"No Route found for {p.id} going to {dst_point.toTuple()}, skipping", flush=True)
            return None

    ########## State Management Methods ##########

    def validateStatusTransition(self, new_status: TricycleStatus) -> bool:
        """
        Validates if a status transition is allowed.
        
        Args:
            new_status: The desired new status
            
        Returns:
            bool: True if transition is valid, False otherwise
        """
        valid_transitions = {
            TricycleStatus.IDLE: [TricycleStatus.SERVING, TricycleStatus.TERMINAL, TricycleStatus.ENQUEUING],
            TricycleStatus.SERVING: [TricycleStatus.RETURNING, TricycleStatus.ROAMING],
            TricycleStatus.TERMINAL: [TricycleStatus.SERVING, TricycleStatus.ENQUEUING],
            TricycleStatus.ROAMING: [TricycleStatus.SERVING, TricycleStatus.ENQUEUING], 
            TricycleStatus.RETURNING: [TricycleStatus.TERMINAL, TricycleStatus.ENQUEUING],
            TricycleStatus.ENQUEUING: [TricycleStatus.SERVING, TricycleStatus.ROAMING, TricycleStatus.IDLE]
        }
        return new_status in valid_transitions.get(self.status, [])

    def updateStatus(self, new_status: TricycleStatus) -> bool:
        """
        Simple function to update tricycle status with validation.
        
        Args:
            new_status: The desired new status
            
        Returns:
            bool: True if status was updated successfully, False otherwise
        """
        if self.validateStatusTransition(new_status):
            self.status = new_status
            return True
        return False

    def finishTrip(self, current_time: int):
        """
        Marks the tricycle as inactive and records the finish event.
        
        Args:
            current_time: Current simulation time
            
        Note:
            Called when tricycle completes route or encounters error
        """
        self.active = False
        self.events.append({
            "type": "FINISH", 
            "time": current_time,
            "location": [self.path[-1].x, self.path[-1].y]
        })
   
   ########## Behavior Methods ##########

    def onCycleComplete(self, current_time: int):
        """
        Called when a tricycle completes a cycle.
        Only changes roam path if tricycle is actively roaming with no passengers.
        """
        # Only increment cycle count if we're actually roaming
        if self.status == TricycleStatus.ROAMING and not self.hasPassenger() and not self.enqueuedPassenger:
            self.cycleCount += 1
            if self.cycleCount >= self.maxCycles:
                self.newRoamPath(current_time)
   
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
            "events": self.events,
            "cycleCount": self.cycleCount,
            "maxCycles": self.maxCycles,
            "status": self.status.value
        }

    def __repr__(self) -> str:
        """Returns a JSON string representation of the tricycle."""
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
        if tricycle.status not in [TricycleStatus.IDLE, TricycleStatus.RETURNING]:
            print(f"Cannot add tricycle {tricycle.id} to terminal: invalid status {tricycle.status}", flush=True)
            return
        self.queue.append(tricycle)
        tricycle.active = False
        if not tricycle.updateStatus(TricycleStatus.TERMINAL):
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