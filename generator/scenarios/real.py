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

from entities import PassengerStatus
from util import NoRoute, get_euclidean_distance, find_path_between_points_in_osrm

from scenarios.util import (
    gen_random_valid_point, 
    get_random_valid_point,
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
    "speed": 0.0000006, 
    "scheduler": smart_scheduler,
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
        - totalTrkes: int - the number of tricycles to be generated. Tricycles are generated at the start of a simulation run,
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
            self.trikeConfig["speed"] = 5.556
            self.trikeConfig["useMeters"] = True
    
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
        # print([(p.y,p.x) for p in validFixedHotspots])
        # # print(list(zip(fixedHotspots, validFixedHotspots)))
        # # validFixedHotspots = fixedHotspots

        # Generate data files
        if not os.path.exists(f"data/real/{run_id}"):
            os.makedirs(f"data/real/{run_id}")
        
        # Setup a new map
        map = entities.Map(
            config.TOP_LEFT_X,
            config.BOT_RIGHT_Y,
            config.BOT_RIGHT_X,
            config.TOP_LEFT_Y,
            20, 20
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
            # Generate roaming tricycles
            if random.random() < self.roamingTrikeChance:
                # find a valid roam path
                # while True:
                #     try:
                #         checkpoints = [x.location for x in random.sample(terminals, k=max(2, len(terminals)))]
                #         checkpoints.insert(1, random.choice(hotspots))
                #         roam_path = gen_random_bnf_roam_path_with_points(*checkpoints)
                #         break
                #     except Exception as e:
                #         print(f"exceptioon! {e}")
                #         continue

                while True:
                    try:
                        if len(terminals) < 2:
                            raise ValueError("Need at least 2 terminals to generate roaming trike.")

                        checkpoints = [x.location for x in random.sample(terminals, k=2)]
                        checkpoints.insert(1, random.choice(hotspots))
                        roam_path = gen_random_bnf_roam_path_with_points(*checkpoints)
                        break
                    except Exception as e:
                        print(f"Retrying path generation due to error: {e}")
                        continue
                trike = entities.Tricycle(
                    id=f"trike_{idx}",
                    roamPath=roam_path,
                    isRoaming=True,
                    startX=roam_path.getStartPoint().x,
                    startY=roam_path.getStartPoint().y,
                    createTime=0,
                    deathTime=-1,
                    map=map,
                    **self.trikeConfig
                )

                print("Generated {} with roam path starting at {}".format(trike.id, roam_path.getStartPoint().toTuple()), flush=True)
            else:
                # spawn in one of the terminals
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
                        raise Exception("Improper trike distrib")
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

            tricycles.append(trike)
        
        # Generate the initial passengers
        passengers_left = self.totalPassengers
        passenger_id = 0
        passengers: list[entities.Passenger] = []

        num_start = round(self.passengerSpawnStartPercent * self.totalPassengers)
        for _ in range(num_start):
            in_terminal = None
            if random.random() < self.roadPassengerChance:
                passenger_source = random.choice(hotspots)
                while True:
                    try:
                        if self.useFixedHotspots:
                            # passenger_dest = entities.Point(*random.choice(validFixedHotspots))
                            passenger_dest = random.choice(validFixedHotspots)
                        else:
                            passenger_dest = gen_random_valid_point()
                        find_path_between_points_in_osrm(passenger_source.toTuple(), passenger_dest.toTuple())
                    except Exception:
                        continue
                    finally:
                        break

                passenger = entities.Passenger(
                    id=f'passenger_{passenger_id}',
                    src=passenger_source,
                    dest=passenger_dest,
                    createTime=0,
                    deathTime=-1
                )

                pp_loc = map.get_loc(*passenger_source.toTuple())
                map.add(pp_loc, passenger)
            else:
                # spawn in one of the terminals
                if self.useFixedHotspots:
                    # passenger_dest = entities.Point(*random.choice(validFixedHotspots))
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
                        raise Exception("Improper passenger distrib")
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

                if in_terminal:
                    in_terminal.addPassenger(passenger)

            print("Generated {} at {} going to {}".format(passenger.id, passenger_source.toTuple(), passenger_dest.toTuple()), flush=True)

            passengers.append(passenger)
            passengers_left -= 1
            passenger_id += 1
        
        # do the actual simulation
        # this is an array to make it a non-primitive object
        cur_time = [0]
        last_active = [-1]

        def process_passenger(passenger: entities.Passenger, trike: entities.Tricycle):
            print("Passenger loaded", passenger.id, "by", trike.id, flush=True)
            passenger.deathTime = cur_time[0]
            passenger.status = PassengerStatus.ONBOARD

        def process_frame():
            """
            Each frames are generated here. You can modify the subtleties of the interactions here.
            """
            
            # Offloading then loading passengers
            for trike in tricycles:
                if not trike.active:
                    continue
                offloaded = list(trike.tryOffload())

                for passenger in offloaded:
                    passenger.offloadTime = cur_time[0]
                    print("----Offloaded", passenger.id, trike.id, flush=True)
                if offloaded:
                    last_active[0] = cur_time[0]

                loaded: list[entities.Passenger] = trike.checkPassengers()

                for passenger in loaded:
                    print("----Loaded", passenger.id, trike.id, flush=True)
                    process_passenger(passenger, trike)
                
            # Moving tricycles
            for trike in tricycles:
                if not trike.active:
                    continue
                try:
                    time_taken = trike.moveTrike()

                    # Trike does not move
                    if not time_taken:
                        offloaded = list(trike.tryOffload())

                        for passenger in offloaded:
                            passenger.offloadTime = cur_time[0]
                            print("----Offloaded", passenger.id, trike.id, flush=True)
                        if offloaded:
                            last_active[0] = cur_time[0]

                        if trike.hasPassenger():
                            print("----Trike didn't move. Will load next passenger", trike.id, flush=True)
                            p = trike.processNextPassenger() 
                            if p is not None:
                                print("--------", p.id)
                            else:
                                print("--------No passenger found")

                        elif not trike.isRoaming:
                            print("----Trike didnt move. Attempting to go to nearest terminal", trike.id, flush=True)
                            nearest_terminal = None
                            nearest_distance = None
                            for terminal in terminals:
                                if map.same_loc(*terminal.location.toTuple(), *trike.curPoint().toTuple()):
                                    print("------Tricycle parked in terminal", trike.id, terminal.location.toTuple(), flush=True)
                                    terminal.addTricycle(trike)
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
                                    trike.addToGo(nearest_terminal.location)
                                except NoRoute:
                                    print("------No Route found. Finishing trip", flush=True)
                                    trike.finishTrip()
                            elif nearest_distance is None:
                                print("------Not able to find any terminal. Finishing trip", flush=True)
                                trike.finishTrip()
                                
                        else:
                            print("----Trike didn't move. Attempting to load next cycle point")
                            trike.loadNextCyclePoint()
                except Exception as e:
                    print(f"Encountered error while trying to move tricycle {trike.id}:", e)
                    print(traceback.format_exc())
                    trike.finishTrip()
                
            for terminal in terminals:
                while (not terminal.isEmptyOfPassengers()) and (not terminal.isEmptyOfTrikes()):
                    loadingResult = terminal.loadTricycle()
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

        end_time = time.time()
        elapsed_time = end_time - start_time

        print("Finished simulation {}. Took {} seconds.".format(run_id, elapsed_time), flush=True)

        last_active[0] += 1 if self.isRealistic else entities.MS_PER_FRAME

        run_metadata["endTime"] = cur_time
        run_metadata["elapsedTime"] = elapsed_time
        run_metadata["lastActivityTime"] = last_active[0]

        # save the metadata
        with open(f"data/real/{run_id}/metadata.json", "w+") as f:
            json.dump(run_metadata, f)
        
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
