# Generator

This folder has the following files and folders. You can use them in the following way:

- `data` - the simulations will output the simulation results here. The latest version of the simulator outputs to the `real` folder.
- `figures` - the dashboard will save the graphs here. This folder was only used for generating graphs used for the manuscript and is not essential to running the simulator.
- `scenarios` - contains the main simulator and utility functions for generating various scenarios. You would likely modify this if you want to modify global interactions (e.g., what to do when tricycles go to terminals, where to spawn the passengers)
- `util` - contains utility classes for handling interactions with OSRM. It's unlikely that you would want to modify this, unless you want to change something about the coordinate system used (e.g., use manhattan distance instead of euclidean distance)
- `__main__.py` - contains the main runner function for the simulator. You would only modify this to setup the general configurations of the runs and running runs.
- `algos.py` - currently only contains the algorithm used for the smart scheduling
- `dashboard.py` - a StreamLit dashboard used to analyze the results of the runs. This dashboard has been tailored to help with writing the manuscript, so it's unlikely that this would be usable out of the box. But, we opted to retain it so that you can have an idea on how to generate graphs/metrics for the runs.
- `entities.py` - contains the models used in the simulation. You would likely modify this if you want to change specific behaviour in a particular entity, usually the tricycle (e.g., how a tricycle should internally manage its passengers).
- `server.py` - a backend FastAPI app used when visualizing the runs. You would need to modify this if you'll change how the simulator generates its data.

