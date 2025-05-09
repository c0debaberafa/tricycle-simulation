import json
import util
from enum import Enum

MS_PER_FRAME = 1000

# PICKUP / DROPOFF PARAMETERS
DETECTION_RADIUS_METERS = 100  # Larger radius for detection
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

    def checkEnqueuedPassengers(self, current_time: int):
        """
        Checks all passengers in the map for enqueue timeouts and resets them if necessary.
        Timeout is based on the speed of the tricycle that claimed the passenger.
        """
        for passenger in self.passengers:
            if passenger.claimed_by:
                # Find the tricycle that claimed this passenger
                for trike in self.tricycles:
                    if trike.id == passenger.claimed_by:
                        if passenger.checkEnqueueTimeout(current_time, trike.speed):
                            print(f"Passenger {passenger.id} enqueue timeout, resetting to WAITING", flush=True)
                            passenger.onReset(current_time, [passenger.src.x, passenger.src.y])
                        break

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
        self.enqueueTime = -1  # Time when passenger was enqueued

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
        self.enqueueTime = time  # Record when passenger was enqueued
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

    def checkEnqueueTimeout(self, current_time: int, trike_speed: float):
        """
        Checks if the passenger has been enqueued for too long without being picked up.
        Timeout is based on how long it would take a tricycle to travel twice the detection radius
        at its current speed, with a minimum timeout of 60 seconds.
        
        Args:
            current_time: Current simulation time in frames
            trike_speed: Speed of the tricycle that claimed this passenger
            
        Returns:
            bool: True if the passenger should be reset
        """
        if self.status == PassengerStatus.ENQUEUED and self.enqueueTime != -1:
            # Calculate timeout based on time to travel 2x detection radius
            # Add minimum timeout of 60 seconds to prevent too frequent resets
            timeout_frames = max(
                (DETECTION_RADIUS_METERS * 2) / (trike_speed * MS_PER_FRAME),
                60  # Minimum 60 second timeout
            )
            return (current_time - self.enqueueTime) > timeout_frames
        return False

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
        self.enqueued_passengers = set()  # Track enqueued passengers
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
            return 0
        
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
        """
        try:
            # Find path to destination
            path = util.find_path_between_points_in_osrm(
                self.path[-1].toTuple(), 
                new_destination.toTuple()
            ) + [new_destination.toTuple()]
            
            # Validate path
            if len(path) < 3:
                print(f"Path too short from {self.path[-1].toTuple()} to {new_destination.toTuple()}, skipping", flush=True)
                return False
            
            # Check for duplicate destinations
            if self.to_go and self.to_go[-1].toTuple() == new_destination.toTuple():
                print(f"Already en route to {new_destination.toTuple()}", flush=True)
                return True
            
            # Convert to Points and update path based on priority
            new_points = [Point(*p) for p in path[1:]]
            
            if priority == 'replace':
                self.to_go = new_points
            elif priority == 'front':
                self.to_go = new_points + self.to_go
            else:  # append
                self.to_go += new_points
            
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

    ########## Passenger Management Methods ##########

    def hasPassenger(self):
        """Returns True if the tricycle has any passengers."""
        return len(self.passengers) > 0

    def enqueueNearbyPassengers(self, current_time: int):
        """
        Detects and claims nearby waiting passengers.
        
        Args:
            current_time: Current simulation time
            
        Returns:
            list[Passenger]: List of newly enqueued passengers
            
        Note:
            - Only considers WAITING passengers
            - Only enqueues as many passengers as the tricycle can load
            - Adds pickup points to front of path
            - Prevents multiple tricycles from claiming the same passenger
        """
        if not self.map:
            raise Exception("Not backward compatible. Please use a map")
        
        cur = self.path[-1]
        
        # Calculate how many more passengers we can take (considering both loaded and enqueued)
        remaining_capacity = self.capacity - (len(self.passengers) + len(self.enqueued_passengers))
        if remaining_capacity <= 0:
            return []
        
        # Get nearby passengers using the new Map method
        nearby_passengers = self.map.getNearbyPassengers(cur, DETECTION_RADIUS_METERS)
        
        enqueued_passengers = []
        for p in nearby_passengers:
            # Stop if we've reached capacity
            if len(enqueued_passengers) >= remaining_capacity:
                break
                
            # Only consider waiting passengers that aren't claimed by other tricycles
            if p.status != PassengerStatus.WAITING:
                continue
            if p.claimed_by is not None and p.claimed_by != self.id:
                continue
                
            # Update passenger status to ENQUEUED and claim them
            p.onEnqueue(self.id, current_time, [p.src.x, p.src.y])
            enqueued_passengers.append(p)
            self.enqueued_passengers.add(p.id)  # Track enqueued passenger
            self.events.append({
                "type": "ENQUEUE",
                "data": p.id,
                "time": current_time,
                "location": [p.src.x, p.src.y]
            })

            # Add pickup point to the front of to_go if not already there
            if not any(point.x == p.src.x and point.y == p.src.y for point in self.to_go):
                if not self.updatePath(p.src, priority='front'):
                    print(f"Failed to add pickup point for {p.id}", flush=True)
        
        return enqueued_passengers

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
        self.enqueued_passengers.discard(p.id)  # Remove from enqueued set
        p.onLoad(self.id, current_time, [self.path[-1].x, self.path[-1].y])
        
        # Only set status to SERVING if not already serving
        if self.status != TricycleStatus.SERVING:
            self.setStatus(TricycleStatus.SERVING)
        return True

    def tryLoad(self, current_time: int):
        """
        Attempts to load enqueued passengers within pickup radius.
        
        Args:
            current_time: Current simulation time
            
        Returns:
            list[Passenger]: List of successfully loaded passengers
            
        Note:
            - Only loads ENQUEUED passengers claimed by this tricycle
            - Resets passengers if loading fails
            - Uses haversine distance for realistic pickup
            - Schedules next passenger's destination after successful load
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
                
                # After loading a passenger, schedule their destination
                try:
                    if self.scheduleNextPassenger():
                        print(f"Scheduled destination for {p.id}", flush=True)
                except NoMorePassengers:
                    print(f"No more passengers to schedule for {self.id}", flush=True)
            else:
                # If we can't load the passenger (e.g., capacity reached),
                # reset their status back to WAITING and clear claim
                print(f"Could not load {p.id} into {self.id}, resetting status to WAITING", flush=True)
                p.onReset(current_time, [p.src.x, p.src.y])
        
        return loaded

    def tryOffload(self, current_time: int):
        """
        Attempts to drop off passengers at their destinations.
        
        Args:
            current_time: Current simulation time
            
        Yields:
            Passenger: Each passenger that was successfully dropped off
            
        Note:
            - Uses haversine distance for realistic dropoff
            - Updates tricycle status after all passengers are dropped
            - Adds wait time after dropoff
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
                if self.status != TricycleStatus.ROAMING:  # Only set if not already in ROAMING
                    self.setStatus(TricycleStatus.ROAMING)
            elif self.status != TricycleStatus.RETURNING_TO_TERMINAL:  # Only set if not already returning
                self.setStatus(TricycleStatus.RETURNING_TO_TERMINAL)
                print(f"Tricycle {self.id} is returning to terminal after dropping off all passengers", flush=True)
        
        # Add a small wait after dropping off passengers to prevent erratic movement
        if dropped:
            self.events.append({
                "type": "WAIT",
                "data": 100,  # Reduced wait time to 100ms
                "time": current_time,
                "location": [self.path[-1].x, self.path[-1].y]
            })

    def scheduleNextPassenger(self):
        """
        Schedules the next passenger to drop off.
        
        Returns:
            Passenger: Next passenger to drop off, or None if no valid path
            
        Note:
            - Uses scheduler if available
            - Replaces current path with path to destination
            - Maintains passenger queue for potential new pickups
        """
        if len(self.passengers) == 0:
            raise NoMorePassengers
        
        # If no scheduler, just offload the first passenger
        if self.scheduler is None:
            p = self.passengers[0]
        else:
            # Get the next passenger to offload from the scheduler
            index, p = self.scheduler(self.path[-1], self.passengers)

        # Get the path to the passenger's destination
        src_point = self.path[-1]
        dst_point = p.dest
        try:
            if not self.updatePath(p.dest, priority='replace'):
                return None
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
            TricycleStatus.IDLE: [TricycleStatus.SERVING, TricycleStatus.TERMINAL],
            TricycleStatus.SERVING: [TricycleStatus.RETURNING_TO_TERMINAL, TricycleStatus.ROAMING],
            TricycleStatus.TERMINAL: [TricycleStatus.SERVING],
            TricycleStatus.ROAMING: [TricycleStatus.SERVING], 
            TricycleStatus.RETURNING_TO_TERMINAL: [TricycleStatus.TERMINAL]
        }
        return new_status in valid_transitions.get(self.status, [])

    def setStatus(self, new_status: TricycleStatus) -> bool:
        """
        Safely changes the tricycle's status.
        
        Args:
            new_status: The desired new status
            
        Returns:
            bool: True if transition was successful, False otherwise
            
        Note:
            - Clears path when transitioning to ROAMING
            - Loads next cycle point for roaming tricycles
        """
        if self.validateStatusTransition(new_status):
            # Clear to_go queue when transitioning to ROAMING
            if new_status == TricycleStatus.ROAMING:
                self.to_go = []
                if self.roamPath:
                    self.loadNextCyclePoint()
                
            self.status = new_status
            return True
        print(f"Invalid status transition for {self.id}: {self.status} -> {new_status}", flush=True)
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