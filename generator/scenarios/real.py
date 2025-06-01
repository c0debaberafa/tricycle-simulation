"""
Contains the frame-by-frame simulator class. Bulk of the simulator
logic is here. If you want to add more scenarios, or add global interactions,
you can modify the Simulator class, specifically, the process_frame function.
"""

import os
import random
import json
import traceback
import string
import time

import config
import entities
import algos

from entities import PassengerStatus, TricycleStatus
from util import NoRoute, get_euclidean_distance, find_path_between_points_in_osrm

from scenarios.util import (
    gen_random_valid_point, 
    gen_random_bnf_roam_path_with_points,
    get_valid_points
)

# TODO: use a logger to make outputting more clean

class ToImplement(Exception):
    pass

class ImproperConfig(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

def generate_random_filename(length=12):
    letters = string.ascii_lowercase
    random_filename = ''.join(random.choice(letters) for _ in range(length))
    return random_filename

def smart_scheduler(src: entities.Point, passengers: list[entities.Passenger]) -> tuple[int, entities.Passenger]:
    """
    A scheduling algorithm used by the tricycle for choosing which passenger
    to process next. This is the smart scheduler described in the paper, and it
    is just a naive scheduler that chooses the current best path. It is good,
    however, it is extremely slow (for large number of passengers).

    If you want to make a new scheduler, make sure it takes in the following 
    parameters:

    - src: entites.Point - the current location of the tricycle
    - passengers: list[entities.Passenger] - the list of the current passengers in the trike

    It must also return the following values:
    - start_index: int - the index of the next passenger that must be processed based on the provided list
    - next_passenger: entities.Passenger - the actual passenger to be processed next
    """
    best_order, start_index = algos.sort_path_brute(src, passengers)
    return start_index, passengers[start_index]

defaultTrikeConfig = {
    "capacity": 3,
    "speed": 5.556,  # Default to meters per second (20 km/h)
    "scheduler": smart_scheduler,
    "useMeters": True  # Always use meters for consistency
}

cache = None

class Simulator:
    def __init__(
            self,
            totalTrikes: int,
            totalTerminals: int,
            totalPassengers: int,
            roadPassengerChance: float = 0.0,
            roamingTrikeChance: float = 0.0,
            terminalPassengerDistrib: list[float] = [],
            terminalTrikeDistrib: list[float] = [],
            passengerSpawnStartPercent: float = 1.0,
            trikeConfig = defaultTrikeConfig,
            hotspots = 2,
            useFixedTerminals = False,
            useFixedHotspots = False,
            useSmartScheduler = True,
            trikeCapacity = None,
            isRealistic = False
        ):
        """
        Parameters:
        - totalTrikes: int - the number of tricycles to be generated. Tricycles are generated at the start of a simulation run,
            so this number is fixed for the duration of a simulation run.
        - totalTerminals: int - the number of terminals to be generated. Terminals are also fixed throughout the simulation
        - totalPassengers: int - the number of passengers to be generated. 
        - roadPassengerChance: float - the chance for passengers to spawn along the road. The value must be in the range [0,1].
            The default value is 0, which means that passengers will spawn in the terminal.
        - roamingTrikeChance: float - the chance for tricycles to roam along the highway. The value must be in the range [0,1].
            The default value is 0, which means that tricycles will wait in terminals instead of roaming when free from
            passengers.
        - terminalPassengerDistrib: list[float] - the distribution of non-road passengers between terminals. The length of the list
            must be the same with the number of terminals. Sample usage:
                [1,2,3] -> terminal 2 will have twice the number of passengers than terminal 1
                        -> terminal 3 will have twice the number of passengers than terminal 2
        - terminalTrikeDistrib: list[float] - the distribution of non-roaming tricycles between terminals. This is similar to
            terminalPassengerDistrib, except for tricycles.
        - passengerSpawnStartPercent: float - the amount of passengers to be generated at the start of the simulation. The default
            value is 1, so it means that all passengers will be generated at the start. This feature is buggy, so it will require
            fixing up before being used.
        - trikeConfig - configurations for the tricycle. Refer to the defaultTrikeConfig for sample on what it looks like
        - hotspots: int - the number of hotspot points to cache for increase in efficiency. No spots are cached by default
        - useFixedTerminals: bool - if True, you must provide a list of terminal locations when running a run. Default to False
        - useFixedHotspots: bool - if True, you must provide a list of points when running a run. Default to False
        - trikeCapacity: int - the number of passengers tricycles can accommodate at a moment
        - isRealistic: bool - always set this to True, unless you want to deal with great circle coordinate system
        """
        self.totalTrikes = totalTrikes
        self.totalTerminals = totalTerminals
        self.totalPassengers = totalPassengers
        self.roadPassengerChance = roadPassengerChance
        self.roamingTrikeChance = roamingTrikeChance
        self.terminalPassengerDistrib = terminalPassengerDistrib
        self.terminalTrikeDistrib = terminalTrikeDistrib
        self.passengerSpawnStartPercent = passengerSpawnStartPercent
        self.trikeConfig = { **trikeConfig }
        self.hotspots = hotspots
        self.useFixedTerminals = useFixedTerminals
        self.useFixedHotspots = useFixedHotspots
        self.useSmartScheduler = useSmartScheduler
        self.prefix = '-'.join([str(x) for x in [totalTrikes, totalTerminals, totalPassengers]])
        self.isRealistic = isRealistic

        # ensure that there are non-negative count of entities
        if self.totalTerminals < 0:
            raise ImproperConfig("Negative number of terminals found")
        if self.totalPassengers < 0:
            raise ImproperConfig("Negative number of passengers found")
        if self.totalTrikes < 0:
            raise ImproperConfig("Negative number of tricycles found")
        
        # ensure the scenario is possible
        if self.totalTerminals == 0:
            if roamingTrikeChance < 1.0 and abs(roamingTrikeChance - 1.0) > 1e-3:
                raise ImproperConfig("Some tricycle will have no behaviour")

        # ensure that the distributions are set properly
        if not len(self.terminalPassengerDistrib) == 0 and not len(self.terminalPassengerDistrib) == totalTerminals:
            raise ImproperConfig("Length of passenger distrib {} does not match number of terminals {}".format(
                len(self.terminalPassengerDistrib),
                self.totalTerminals
            ))
        if not len(self.terminalTrikeDistrib) == 0 and not len(self.terminalTrikeDistrib) == totalTrikes:
            raise ImproperConfig("Length of terminal trike distrib {} does not match the number of terminals {}".format(
                len(self.terminalTrikeDistrib),
                self.totalTerminals
            ))
        
        self.hotspotsCache = cache

        if not useSmartScheduler:
            self.trikeConfig["scheduler"] = None
        if trikeCapacity is not None:
            self.trikeConfig["capacity"] = trikeCapacity
        if isRealistic:
            self.trikeConfig["speed"] = 5.556  # 20 km/h in meters per second
            self.trikeConfig["useMeters"] = True
        else:
            # Convert to degrees per frame for non-realistic mode
            # 5.556 m/s * (1 degree/111000m) * (1s/1000ms) = 0.00005 degrees per frame
            self.trikeConfig["speed"] = 0.00005
            self.trikeConfig["useMeters"] = False
    
    def run(
            self, 
            seed=None, 
            maxTime=50_000, 
            dataPath=None, 
            fixedTerminals=[], 
            fixedHotspots=[]):
        """
        This generates a new simulation.
        """

        global cache

        run_id = f'{self.prefix}-{generate_random_filename()}'
        run_metadata = {
            "id": run_id,
            "seed": seed,
            "maxTime": maxTime,
            "totalTrikes": self.totalTrikes,
            "totalPassengers": self.totalPassengers,
            "totalTerminals": self.totalTerminals,
            "roadPassengerChance": self.roadPassengerChance,
            "roamingTrikeChance": self.roamingTrikeChance,
            "hotspots": self.hotspots,
            "smartScheduling": self.useSmartScheduler,
            "isRealistic": self.isRealistic,
            "trikeConfig": {
                "capacity": self.trikeConfig["capacity"],
                "speed": self.trikeConfig["speed"]
            }
        }

        if seed is not None:
            random.seed(seed)
        
        print(f"Running with the following metadata:", run_metadata, flush=True)
        start_time = time.time()

        if self.hotspotsCache:
            validFixedHotspots = self.hotspotsCache
        else:
            validFixedHotspots = get_valid_points(fixedHotspots)
            self.hotspotsCache = validFixedHotspots
            cache = validFixedHotspots

        # Generate data files
        if not os.path.exists(f"data/real/{run_id}"):
            os.makedirs(f"data/real/{run_id}")
        
        # Setup a new map
        map = entities.Map(
            config.TOP_LEFT_X,
            config.BOT_RIGHT_Y,
            config.BOT_RIGHT_X,
            config.TOP_LEFT_Y
        )

        hotspots: list[entities.Point] = [gen_random_valid_point() for _ in range(self.hotspots)]

        # Generate terminals
        terminals: list[entities.Terminal] = []

        if self.useFixedTerminals:
            for y,x in fixedTerminals:
                terminal_loc = entities.Point(x,y)
                print("Generated Terminal at", terminal_loc, flush=True)
                terminal = entities.Terminal(
                    location=terminal_loc,
                    capacity=20
                )
                terminals.append(terminal)
        else:
            for idx in range(self.totalTerminals):
                terminal_loc = gen_random_valid_point()
                print("Generated Terminal at", terminal_loc, flush=True)
                terminal = entities.Terminal(
                    location=terminal_loc,
                    capacity=100
                )
                terminals.append(terminal)
        
        # Generate tricycles
        tricycles: list[entities.Tricycle] = []
        for idx in range(self.totalTrikes):
            trike = None
            in_terminal: entities.Terminal = None
            if random.random() < self.roamingTrikeChance:
                # Generate roaming tricycle with temporary path
                start_hotspot = random.choice(hotspots)  # Randomly select starting hotspot
                trike = entities.Tricycle(
                    id=f"trike_{idx}",
                    roamPath=None,  # Start with no path
                    isRoaming=True,
                    startX=start_hotspot.x,  # Use random hotspot position
                    startY=start_hotspot.y,
                    createTime=0,
                    deathTime=-1,
                    map=map,
                    maxCycles=5,
                    **self.trikeConfig
                )
                
                # Generate initial roam path
                if trike.newRoamPath(0):  # Pass current_time=0
                    print(f"Generated {trike.id} with initial roam path at {start_hotspot.toTuple()}", flush=True)
                else:
                    print(f"Failed to generate initial roam path for {trike.id}", flush=True)
            else:
                # Generate non-roaming tricycles at terminals
                if len(self.terminalTrikeDistrib):
                    trike_source = None
                    x = random.random()
                    for terminal, chance in zip(terminals, self.terminalTrikeDistrib):
                        if x < chance:
                            trike_source = entities.Point(*terminal.location.toTuple())
                            in_terminal = terminal
                            break
                        else:
                            x -= chance
                    
                    if trike_source is None:
                        raise Exception("Improper trike distribution")
                else:
                    in_terminal = random.choice(terminals)
                    trike_source = entities.Point(*in_terminal.location.toTuple())
                
                trike = entities.Tricycle(
                    id=f"trike_{idx}",
                    roamPath=None,
                    isRoaming=False,
                    startX=trike_source.x,
                    startY=trike_source.y,
                    createTime=0,
                    deathTime=-1,
                    map=map,
                    **self.trikeConfig
                )

                if in_terminal:
                    in_terminal.addTricycle(trike)

                print("Generated {} at {}".format(trike.id, trike_source.toTuple()), flush=True)

            map.addTricycle(trike)
            tricycles.append(trike)
        
        # Generate passengers
        # By design, passengers are generated at the start of the simulation
        # If you want to implement passengers being generated throughout the simulation,
        # you will need to modify this
        passenger_id = 0
        passengers: list[entities.Passenger] = []

        for _ in range(self.totalPassengers):
            in_terminal = None
            if random.random() < self.roadPassengerChance:
                # Generate road passenger on the road
                # passenger_source = random.choice(hotspots)
                while True:
                    try:
                        passenger_source = gen_random_valid_point()
                        if self.useFixedHotspots:
                            passenger_dest = random.choice(validFixedHotspots)
                        else:
                            passenger_dest = gen_random_valid_point()
                        find_path_between_points_in_osrm(passenger_source.toTuple(), passenger_dest.toTuple())
                        break
                    except Exception:
                        continue

                passenger = entities.Passenger(
                    id=f'passenger_{passenger_id}',
                    src=passenger_source,
                    dest=passenger_dest,
                    createTime=0,
                    deathTime=-1
                )

                # Road passengers only go to map
                map.addPassenger(passenger)
            else:
                # Generate terminal passenger
                if self.useFixedHotspots:
                    passenger_dest = random.choice(validFixedHotspots)
                else:
                    passenger_dest = gen_random_valid_point()
                if len(self.terminalPassengerDistrib):
                    passenger_source = None
                    x = random.random()
                    for terminal, chance in zip(terminals, self.terminalPassengerDistrib):
                        if x < chance:
                            passenger_source = entities.Point(*terminal.location.toTuple())
                            in_terminal = terminal
                            break
                        else:
                            x -= chance
                    
                    if passenger_source is None:
                        raise Exception("Improper passenger distribution")
                else:
                    in_terminal = random.choice(terminals)
                    passenger_source = entities.Point(*in_terminal.location.toTuple())
                
                passenger = entities.Passenger(
                    id=f'passenger_{passenger_id}',
                    src=passenger_source,
                    dest=passenger_dest,
                    createTime=0,
                    deathTime=-1
                )

                # Add passenger to both terminal and map
                if in_terminal:
                    in_terminal.addPassenger(passenger)
                map.addPassenger(passenger)  # Add all passengers to map

            print("Generated {} at {} going to {}".format(passenger.id, passenger_source.toTuple(), passenger_dest.toTuple()), flush=True)

            passengers.append(passenger)
            passenger_id += 1
        
        # do the actual simulation
        # this is an array to make it a non-primitive object
        cur_time = [0]
        last_active = [-1]

        def process_passenger(passenger: entities.Passenger, trike: entities.Tricycle):
            print("Passenger loaded", passenger.id, "by", trike.id, flush=True)
            passenger.pickupTime = cur_time[0]
            passenger.status = PassengerStatus.ONBOARD

        def process_frame():
            """
            Each frame is generated here. You can modify the subtleties of the interactions here.
            """
            
            # 1. First detect nearby passengers and plan routes
            for trike in tricycles:
                if not trike.active:
                    continue
                # Only roaming tricycles should look for passengers on the road
                if trike.isRoaming:
                    p = trike.enqueueNearbyPassenger(cur_time[0])
                    if p:
                        print(f"----Detected passenger {p.id} for {trike.id}", flush=True)
            
            # 2. Handle offloading/loading
            for trike in tricycles:
                if not trike.active:
                    continue

                # Offloading
                offloaded = list(trike.tryOffload(cur_time[0]))

                for passenger in offloaded:
                    print("----Offloaded", passenger.id, trike.id, flush=True)
                if offloaded:
                    last_active[0] = cur_time[0]

                # Loading
                loaded: list[entities.Passenger] = trike.tryLoad(cur_time[0])

                for passenger in loaded:
                    print("----Loaded", passenger.id, trike.id, flush=True)
                    process_passenger(passenger, trike)
                
            # 3. Move tricycles
            for trike in tricycles:
                if not trike.active:
                    continue
                try:
                    time_taken = trike.moveTrike(cur_time[0])

                    # Trike does not move
                    if not time_taken:
                        offloaded = list(trike.tryOffload(cur_time[0]))

                        for passenger in offloaded:
                            print("----Offloaded", passenger.id, trike.id, flush=True)
                        if offloaded:
                            last_active[0] = cur_time[0]

                        if trike.hasPassenger():
                            print("----Trike didn't move. Will load next passenger", trike.id, flush=True)
                            p = trike.scheduleNextPassenger() 
                            if p is not None:
                                print("--------", p.id)
                            else:
                                print("--------No passenger found")

                        elif not trike.isRoaming:
                            print("----Trike didnt move. Attempting to go to nearest terminal", trike.id, flush=True)
                            nearest_terminal = None
                            nearest_distance = None
                            for terminal in terminals:
                                # Only consider a tricycle to be at a terminal if:
                                # 1. It's physically close enough, AND
                                # 2. It's in a state where it can be picked up by a terminal
                                is_at_terminal = (
                                    map.isAtLocation(terminal.location, trike.curPoint()) and 
                                    trike.status in [TricycleStatus.IDLE, TricycleStatus.RETURNING]
                                )
                                if is_at_terminal:
                                    print("------Tricycle parked in terminal", trike.id, terminal.location.toTuple(), flush=True)
                                    terminal.addTricycle(trike)
                                    trike.status = TricycleStatus.TERMINAL
                                    nearest_terminal = None
                                    nearest_distance = -1
                                    break
                                elif nearest_terminal is None or \
                                    get_euclidean_distance(trike.curPoint().toTuple(), terminal.location.toTuple()) < nearest_distance:
                                    nearest_terminal = terminal
                                    nearest_distance = get_euclidean_distance(trike.curPoint().toTuple(), terminal.location.toTuple())
                            if nearest_terminal is not None:
                                print("------Found nearest terminal", nearest_terminal.location.toTuple(), flush=True)
                                try:
                                    if not trike.updatePath(nearest_terminal.location, priority='front'):
                                        print("------No Route found. Finishing trip", flush=True)
                                        trike.finishTrip(cur_time[0])
                                except util.NoRoute:
                                    print("------No Route found. Finishing trip", flush=True)
                                    trike.finishTrip(cur_time[0])
                            elif nearest_distance is None:
                                print("------Not able to find any terminal. Finishing trip", flush=True)
                                trike.finishTrip(cur_time[0])
                                
                        else:
                            print("----Trike didn't move. Attempting to load next cycle point")
                            # Call onCycleComplete before loading next point
                            trike.onCycleComplete(cur_time[0])
                            trike.loadNextCyclePoint()
                except Exception as e:
                    print(f"Encountered error while trying to move tricycle {trike.id}:", e)
                    print(traceback.format_exc())
                    trike.finishTrip(cur_time[0])
                
            for terminal in terminals:
                while (not terminal.isEmptyOfPassengers()) and (not terminal.isEmptyOfTrikes()):
                    loadingResult = terminal.loadTricycle(cur_time[0])
                    if len(loadingResult["passengers"]) == 0:
                        break
                    for passenger in loadingResult["passengers"]:
                        process_passenger(passenger, loadingResult["tricycle"])
                    terminal.popTricycle()
            
            # update the time
            cur_time[0] += 1 if self.isRealistic else entities.MS_PER_FRAME

        print("Running the simulation...", flush=True)

        while cur_time[0] < maxTime:
            process_frame()
            
            # Check if all passengers have completed their trips
            all_passengers_completed = all(passenger.status == PassengerStatus.COMPLETED for passenger in passengers)
            if all_passengers_completed:
                print("All passengers have completed their trips. Ending simulation early.", flush=True)
                break

        end_time = time.time()
        elapsed_time = end_time - start_time

        print("Finished simulation {}. Took {} seconds.".format(run_id, elapsed_time), flush=True)

        # Calculate summary statistics
        completed_trips = 0
        total_wait_time = 0
        total_travel_time = 0
        total_distance = 0
        total_productive_distance = 0
        active_tricycles = 0

        # Process passenger statistics
        for passenger in passengers:
            if passenger.status == PassengerStatus.COMPLETED:
                completed_trips += 1
                total_wait_time += passenger.pickupTime - passenger.createTime
                total_travel_time += passenger.deathTime - passenger.pickupTime

        # Process tricycle statistics
        for trike in tricycles:
            if trike.active:
                active_tricycles += 1
            total_distance += trike.totalDistanceM
            total_productive_distance += trike.totalProductiveDistanceM

        # Print summary
        print("\nSimulation Summary:")
        print("------------------")
        print(f"Total Trips Completed: {completed_trips}")
        print(f"Completion Rate: {(completed_trips/self.totalPassengers)*100:.1f}%")
        print(f"Average Wait Time: {total_wait_time/completed_trips if completed_trips > 0 else 0:.1f} seconds")
        print(f"Average Travel Time: {total_travel_time/completed_trips if completed_trips > 0 else 0:.1f} seconds")
        print(f"Total Distance Traveled: {total_distance/1000:.1f} km")
        print(f"Productive Distance: {total_productive_distance/1000:.1f} km")
        print(f"Efficiency: {(total_productive_distance/total_distance)*100:.1f}%")
        print(f"Active Tricycles: {active_tricycles}/{self.totalTrikes}")
        print("------------------")

        # Return summary statistics
        summary_stats = {
            "total_trips_completed": completed_trips,
            "completion_rate": (completed_trips/self.totalPassengers)*100,
            "average_wait_time": total_wait_time/completed_trips if completed_trips > 0 else 0,
            "average_travel_time": total_travel_time/completed_trips if completed_trips > 0 else 0,
            "total_distance_km": total_distance/1000,
            "productive_distance_km": total_productive_distance/1000,
            "efficiency_percentage": (total_productive_distance/total_distance)*100,
            "active_tricycles": active_tricycles,
            "total_tricycles": self.totalTrikes,
            "simulation_parameters": {
                "total_trikes": self.totalTrikes,
                "total_terminals": self.totalTerminals,
                "total_passengers": self.totalPassengers,
                "use_smart_scheduler": self.useSmartScheduler,
                "trike_capacity": self.trikeConfig["capacity"],
                "is_realistic": self.isRealistic,
                "use_fixed_hotspots": self.useFixedHotspots,
                "use_fixed_terminals": self.useFixedTerminals,
                "road_passenger_chance": self.roadPassengerChance,
                "roaming_trike_chance": self.roamingTrikeChance
            }
        }

        # Write summary statistics to file
        with open(f"data/real/{run_id}/summary.json", "w+") as f:
            json.dump(summary_stats, f, indent=2)

        last_active[0] += 1 if self.isRealistic else entities.MS_PER_FRAME

        run_metadata["endTime"] = cur_time
        run_metadata["elapsedTime"] = elapsed_time
        run_metadata["lastActivityTime"] = last_active[0]

        # save the metadata
        with open(f"data/real/{run_id}/metadata.json", "w+") as f:
            json.dump(run_metadata, f)
        
        # save all terminal data in a single file
        terminals_data = []
        for idx, terminal in enumerate(terminals):
            terminal_data = {
                "id": f"terminal_{idx}",
                "location": terminal.location.toTuple(),
                "capacity": terminal.capacity,
                "remaining_passengers": len(terminal.passengers),
                "remaining_tricycles": len(terminal.queue)
            }
            terminals_data.append(terminal_data)
        with open(f"data/real/{run_id}/terminals.json", "w+") as f:
            json.dump(terminals_data, f)
        
        # save roam endpoints for roaming tricycles
        roam_endpoints = []
        for trike in tricycles:
            if trike.isRoaming and trike.roamPath:
                roam_data = {
                    "tricycle_id": trike.id,
                    "start_point": trike.roamPath.getStartPoint().toTuple(),
                    "end_point": trike.roamPath.path[-1].toTuple(),
                    "checkpoints": [point.toTuple() for point in trike.roamPath.path]
                }
                roam_endpoints.append(roam_data)
        
        with open(f"data/real/{run_id}/roam_endpoints.json", "w+") as f:
            json.dump(roam_endpoints, f)
        
        # save the tricycles
        for trike in tricycles:
            trike.deathTime = last_active[0]
            trike.waitingTime = last_active[0] - trike.totalDistance / trike.speed
            with open(f"data/real/{run_id}/{trike.id}.json", "w+") as f:
                f.write(repr(trike))
        
        # save remaining passengers
        for passenger in passengers:
            with open(f"data/real/{run_id}/{passenger.id}.json", "w+") as f:
                f.write(repr(passenger))
        
        return summary_stats
