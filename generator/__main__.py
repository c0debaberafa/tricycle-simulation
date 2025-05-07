import config

from scenarios.real import Simulator

if __name__ == '__main__':
    # these are the basic parameters if you want to
    # simulate simple non-roaming cases. For more complex
    # cases, you would need to consult the code in more details
    NUM_TRIKES = 3
    NUM_TERMINALS = 2
    NUM_PASSENGERS = 10
    MAX_TIME = 3_600
    TEST_COUNT = 1
    
    # you can look at the code of Simulator for more options
    simulator = Simulator(
        totalTrikes=NUM_TRIKES,
        totalTerminals=NUM_TERMINALS,
        totalPassengers=NUM_PASSENGERS,
        roadPassengerChance=0.5,
        roamingTrikeChance=0.5,
        useFixedHotspots=True, # only use if you have setup hotspots in config
        useFixedTerminals=False, # only use if you have setup hotspots in config
        useSmartScheduler=True,
        trikeCapacity=3,
        isRealistic=True # always set to true
    )
    for _ in range(TEST_COUNT):
        simulator.run(maxTime=MAX_TIME, fixedHotspots=config.MAGIN_HOTSPOTS, fixedTerminals=config.MAGIN_TERMINALS)
