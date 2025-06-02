import config

from scenarios.real import Simulator, defaultTrikeConfig

if __name__ == '__main__':
    # these are the basic parameters if you want to
    # simulate simple non-roaming cases. For more complex
    # cases, you would need to consult the code in more details
    NUM_TRIKES = 15
    NUM_TERMINALS = 2
    NUM_PASSENGERS = 200
    MAX_TIME = 5_000 
    TEST_COUNT = 1
    
    # Simulation parameters
    S_ENQUEUE_RADIUS_METERS = 50  # Radius for enqueueing when tricycle is serving passengers
    ENQUEUE_RADIUS_METERS = 200  # Radius for enqueueing when tricycle is not serving passengers
    MAX_CYCLES = 1  # Maximum number of cycles a tricycle can roam without picking up passengers
    
    # Create custom trike config
    trike_config = {**defaultTrikeConfig}
    trike_config.update({
        "capacity": 3,
        "s_enqueue_radius_meters": S_ENQUEUE_RADIUS_METERS,
        "enqueue_radius_meters": ENQUEUE_RADIUS_METERS,
        "maxCycles": MAX_CYCLES
    })
    
    # you can look at the code of Simulator for more options
    simulator = Simulator(
        totalTrikes=NUM_TRIKES,
        totalTerminals=NUM_TERMINALS,
        totalPassengers=NUM_PASSENGERS,
        roadPassengerChance=1.0,
        roamingTrikeChance=1.0,
        useFixedHotspots=True, # only use if you have setup hotspots in config
        useFixedTerminals=False, # only use if you have setup hotspots in config
        useSmartScheduler=True,
        trikeConfig=trike_config,
        isRealistic=True # always set to true
    )
    for _ in range(TEST_COUNT):
        simulator.run(maxTime=MAX_TIME, fixedHotspots=config.MAGIN_HOTSPOTS, fixedTerminals=config.MAGIN_TERMINALS)
