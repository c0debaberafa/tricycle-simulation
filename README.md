# Tricycle Trip with Multiple Passengers Modeling

## Objective

To be able to create a simulation software which can aid in determining the optimal tricycle scheduling in order to maximize drivers' profit per time working and minimize passengers' waiting time. Specifically:

- Be able to simulate the behavior of tricycle trips that can handle multiple passengers
- Be able to configure the characteristics of the tricycle and passengers
- Measure the driver's total time in a _income-generating trip_
- Measure passengers' waiting time and total trip time
- Be able to visualize the results of the simulation

## How to use and modify this codebase

There are three main folders in this codebase:
- `generator` - this contains the bulk of the logic of the simulation. If you want to modify simulation behaviour, it is likely that you would need to modify the files here.
- `visualization` - this contains the web app for providing simple visualization to the simulations. Currently, it is very rudimentary and lacks features for proper usage. 
- `osrm-backend` - this contains the code for running the OSRM that have been setup so far. You can replace this with your own OSRM server. Just make sure to update the endpoints in the codes.

## OSRM

The OSRM can only run through a Linux shell, so make sure to have WSL installed and setup with a Linux distro. To start the server, run the following command:

```bash
build/osrm-routed maps/magin/map_magin.osm
```

If you want to setup your own OSRM and use a different map, follow this [tutorial](https://www.r-bloggers.com/2017/09/building-a-local-osrm-instance/). If you're using Windows, you must use WSL when setting this up. Make sure to take note of the coordinates use and update `generator/config.py`.

API documentation can be found at https://project-osrm.org/docs/v5.24.0/api/#

## Simulation Generator

The Simulation Generator (simply `generator`) is a Python programmed designed to run the core simulations. 

### Data Generation

To run the simulation and generate the necessary data, go inside the `generator` folder and run the following command:

```bash
python __main__.py
```

You can modify `__main__.py` to configure the Simulator class.

### Data Server

To start the server needed by the simulation visualization, go to the `generator` folder and run the following command:

```bash
flask --app server run --port=5050
```

## Simulation Visualization

The Simulation Visualization (simply `visualization`) is a web application designed to show a visualization of the results of the `generator`. It uses the [LeafletJS](https://leafletjs.com/) library to generate the interactive map.

To start the server, ensure that `npm serve` is installed and run the following command:

```bash
serve .
```

Make sure to update `visualization/js/map.js` to use the run ID you would like to visualize.

## Other Things to Consider

- Explore other OSRMs
- Explore other ways of obtaining paths

## Current Limitations

We are currently working on generated data which is not yet part of actual studies or surveys. This may limit the realism that the simulation provide.

## Important Links:

[LeafletJS Documation](https://leafletjs.com/reference.html) - used to code the visualization

[OSRM Local Server Setup](https://www.r-bloggers.com/2017/09/building-a-local-osrm-instance/) - used to setup the OSRM needed to generate the data

[Map Used](https://www.openstreetmap.org/export#map=16/14.6433/121.0566&layers=N) - the osrm file used

[OSRM Server Documentation](https://project-osrm.org/docs/v5.24.0/api/#) - the API documentation for the OSRM server