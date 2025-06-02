import os
import json
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from datetime import datetime

class SimulationRun:
    def __init__(self, run_dir):
        """Initialize from a simulation run directory"""
        self.run_dir = run_dir
        
        # Load metadata
        with open(os.path.join(run_dir, 'metadata.json'), 'r') as f:
            metadata = json.load(f)
            self.metadata = metadata
            self.numTrikes = metadata['totalTrikes']
            self.useSmartScheduler = metadata['smartScheduling']
            self.trikeCapacity = metadata['trikeConfig']['capacity']
            self.s_enqueue_radius = metadata['trikeConfig']['s_enqueue_radius_meters']
            self.enqueue_radius = metadata['trikeConfig']['enqueue_radius_meters']
            self.maxCycles = metadata['trikeConfig']['maxCycles']
        
        # Load summary statistics
        with open(os.path.join(run_dir, 'summary.json'), 'r') as f:
            self.summary = json.load(f)
        
        # Load passenger data
        self.passengers = []
        for filename in os.listdir(run_dir):
            if filename.startswith('passenger_') and filename.endswith('.json'):
                with open(os.path.join(run_dir, filename), 'r') as f:
                    passenger_data = json.load(f)
                    passenger = {
                        "waitingTime": passenger_data['pickupTime'] - passenger_data['createTime'],
                        "travelingTime": passenger_data['deathTime'] - passenger_data['pickupTime'],
                        "waitingTimeSeconds": passenger_data['pickupTime'] - passenger_data['createTime'],
                        "travelingTimeSeconds": passenger_data['deathTime'] - passenger_data['pickupTime']
                    }
                    self.passengers.append(passenger)
        
        # Load tricycle data
        self.trikes = []
        for filename in os.listdir(run_dir):
            if filename.startswith('trike_') and filename.endswith('.json'):
                with open(os.path.join(run_dir, filename), 'r') as f:
                    trike_data = json.load(f)
                    trike = {
                        "totalDistance": trike_data['totalDistance'],
                        "productiveDistance": trike_data['productiveDistance'],
                        "waitingTimeSeconds": max(0, trike_data['waitingTime']),
                        "speed": trike_data['speed'],
                        "productiveTravelTimeSeconds": trike_data['totalProductiveDistanceM']/trike_data['speed'],
                        "unproductiveTravelTimeSeconds": (trike_data['totalDistance']-trike_data['productiveDistance'])/trike_data['speed']
                    }
                    trike["totalTimeSeconds"] = trike["waitingTimeSeconds"] + trike["productiveTravelTimeSeconds"] + trike["unproductiveTravelTimeSeconds"]
                    self.trikes.append(trike)

def plot_metric(sims, x_values, x_label, title_prefix, fig_name):
    """Helper function to create a plot for a specific metric"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot waiting time
    y_values = [sum([p["waitingTimeSeconds"] for p in x.passengers])/len(x.passengers) for x in sims]
    sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values}), 
                ci=None, ax=ax)
    ax.set_xlabel(x_label)
    ax.set_ylabel("Average Passenger Waiting Time (s)")
    ax.set_title(f"{title_prefix} vs Average Passenger Waiting Time")
    ax.grid(True)
    plt.savefig(f'figures/fig{fig_name}1.png', bbox_inches='tight')
    plt.close()
    
    # Plot traveling time
    fig, ax = plt.subplots(figsize=(10, 6))
    y_values = [sum([p["travelingTimeSeconds"] for p in x.passengers])/len(x.passengers) for x in sims]
    sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values}), 
                ci=None, ax=ax)
    ax.set_xlabel(x_label)
    ax.set_ylabel("Average Passenger Traveling Time (s)")
    ax.set_title(f"{title_prefix} vs Average Passenger Traveling Time")
    ax.grid(True)
    plt.savefig(f'figures/fig{fig_name}2.png', bbox_inches='tight')
    plt.close()
    
    # Plot productive time
    fig, ax = plt.subplots(figsize=(10, 6))
    y_values = [sum([t["productiveTravelTimeSeconds"]/t["totalTimeSeconds"] for t in x.trikes])/len(x.trikes) for x in sims]
    sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values}), 
                ci=None, ax=ax)
    ax.set_xlabel(x_label)
    ax.set_ylabel("Average Tricycle Productive Time (%)")
    ax.set_title(f"{title_prefix} vs Average Tricycle Productive Time")
    ax.grid(True)
    plt.savefig(f'figures/fig{fig_name}3.png', bbox_inches='tight')
    plt.close()

def main():
    # Create figures directory if it doesn't exist
    os.makedirs('figures', exist_ok=True)
    
    # Load simulation results
    print("\nLoading simulation results...")
    simulations = []
    
    # Look for simulation directories
    data_dir = os.path.join('data', 'real')
    for run_dir in os.listdir(data_dir):
        run_path = os.path.join(data_dir, run_dir)
        if os.path.isdir(run_path) and not run_dir.startswith('.'):
            try:
                simulation = SimulationRun(run_path)
                simulations.append(simulation)
                print(f"Loaded simulation with {simulation.numTrikes} tricycles, capacity {simulation.trikeCapacity}")
            except Exception as e:
                print(f"Failed to load simulation {run_dir}: {str(e)}")
                continue

    print(f"\nTotal simulations loaded: {len(simulations)}")
    
    if len(simulations) == 0:
        print("\nNo valid simulations found! Check the following:")
        print("1. Are there any simulation results in data/real/ directory?")
        print("2. Do the simulation results have the correct format?")
        return

    # Filter valid simulations (100 passengers)
    valid_simulations = list(filter(lambda x: len(x.passengers) == 100, simulations))
    print(f"\nValid simulations after filtering: {len(valid_simulations)}")
    
    if len(valid_simulations) == 0:
        print("\nNo valid simulations found! Check the following:")
        print("1. Are there any simulations with 100 passengers?")
        return

    # Group A: Number of tricycles (smart scheduling, capacity 3, s_radius=50, e_radius=100, maxCycles=2)
    group_a_sims = [x for x in valid_simulations 
                   if x.useSmartScheduler 
                   and x.trikeCapacity == 3 
                   and x.s_enqueue_radius == 50 
                   and x.enqueue_radius == 100 
                   and x.maxCycles == 2]
    if group_a_sims:
        x_values = [x.numTrikes for x in group_a_sims]
        plot_metric(group_a_sims, x_values, "Number of Tricycles", "Number of Tricycles", "A")
        print(f"Generated Group A figures (Number of Tricycles) - {len(group_a_sims)} simulations")
        print(f"Found tricycle counts: {sorted(set(x_values))}")

    # Group B: Tricycle capacity (smart scheduling, trikes=9, s_radius=50, e_radius=100, maxCycles=2)
    group_b_sims = [x for x in valid_simulations 
                   if x.useSmartScheduler 
                   and x.numTrikes == 9 
                   and x.s_enqueue_radius == 50 
                   and x.enqueue_radius == 100 
                   and x.maxCycles == 2]
    if group_b_sims:
        x_values = [x.trikeCapacity for x in group_b_sims]
        plot_metric(group_b_sims, x_values, "Tricycle Capacity", "Tricycle Capacity", "B")
        print(f"Generated Group B figures (Tricycle Capacity) - {len(group_b_sims)} simulations")
        print(f"Found capacities: {sorted(set(x_values))}")

    # Group C: Enqueue radius (smart scheduling, trikes=9, capacity=3, s_radius=50, maxCycles=2)
    group_c_sims = [x for x in valid_simulations 
                   if x.useSmartScheduler 
                   and x.numTrikes == 9 
                   and x.trikeCapacity == 3 
                   and x.s_enqueue_radius == 50 
                   and x.maxCycles == 2]
    if group_c_sims:
        x_values = [x.enqueue_radius for x in group_c_sims]  # Changed from s_enqueue_radius to enqueue_radius
        plot_metric(group_c_sims, x_values, "Enqueue Radius (meters)", "Enqueue Radius", "C")
        print(f"Generated Group C figures (Enqueue Radius) - {len(group_c_sims)} simulations")
        print(f"Found enqueue radii: {sorted(set(x_values))}")

    # Group D: Serving enqueue radius (smart scheduling, trikes=9, capacity=3, e_radius=100, maxCycles=2)
    group_d_sims = [x for x in valid_simulations 
                   if x.useSmartScheduler 
                   and x.numTrikes == 9 
                   and x.trikeCapacity == 3 
                   and x.enqueue_radius == 100 
                   and x.maxCycles == 2]
    if group_d_sims:
        x_values = [x.s_enqueue_radius for x in group_d_sims]
        plot_metric(group_d_sims, x_values, "Serving Enqueue Radius (meters)", "Serving Enqueue Radius", "D")
        print(f"Generated Group D figures (Serving Enqueue Radius) - {len(group_d_sims)} simulations")
        print(f"Found serving enqueue radii: {sorted(set(x_values))}")

    print("\nAll figures have been generated in the 'figures' directory")

if __name__ == '__main__':
    main() 