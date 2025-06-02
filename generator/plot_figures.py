import os
import json
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from datetime import datetime

class SimulationRun:
    def __init__(self, name):
        self.name = name
        try:
            numTrikes, numTerminals, numPassengers, seed = name.split('-')
            self.numTrikes = int(numTrikes)
            self.numTerminals = int(numTerminals)
            self.numPassengers = int(numPassengers)
            self.seed = seed
        except ValueError:
            # Handle new format with timestamp
            parts = name.split('-')
            self.numTrikes = int(parts[0])
            self.numTerminals = int(parts[1])
            self.numPassengers = int(parts[2])
            self.seed = parts[3]

        with open(os.path.join('data', 'real', self.name, 'metadata.json')) as f:
            self.metadata = json.load(f)
        
        # validate if metadata is updated
        if 'isRealistic' not in self.metadata:
            raise Exception("Not realistic")
        if 'lastActivityTime' not in self.metadata:
            raise Exception("Wrong metadata")
        if 'smartScheduling' not in self.metadata:
            raise Exception("Wrong metadata")
        
        self.trikeCapacity = self.metadata['trikeConfig'].get('capacity', 3)
        self.useSmartScheduler = self.metadata.get('smartScheduling', True)

        self.trikes = []
        for i in range(self.numTrikes):
            with open(os.path.join('data', 'real', self.name, f'trike_{i}.json')) as f:
                data = json.load(f)
                trike = {
                    "totalDistance": data["totalDistance"],
                    "productiveDistance": data["productiveDistance"],
                    "waitingTimeSeconds": max(0, data["waitingTime"]),
                    "speed": data["speed"],
                    "productiveTravelTimeSeconds": data["totalProductiveDistanceM"]/data["speed"],
                    "unproductiveTravelTimeSeconds": (data["totalDistance"]-data["productiveDistance"])/data["speed"]
                }
                trike["totalTimeSeconds"] = trike["waitingTimeSeconds"] + trike["productiveTravelTimeSeconds"] + trike["unproductiveTravelTimeSeconds"]
                self.trikes.append(trike)

        self.passengers = []
        for i in range(self.numPassengers):
            try:
                with open(os.path.join('data', 'real', self.name, f'passenger_{i}.json')) as f:
                    data = json.load(f)
                    passenger = {
                        "waitingTime": data["pickupTime"] - data["createTime"],
                        "travelingTime": data["deathTime"] - data["pickupTime"],
                        "waitingTimeSeconds": data["pickupTime"] - data["createTime"],
                        "travelingTimeSeconds": data["deathTime"] - data["pickupTime"]
                    }
                    self.passengers.append(passenger)
            except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
                continue

def main():
    # Create figures directory if it doesn't exist
    os.makedirs('figures', exist_ok=True)
    
    # Generate timestamp for new figures
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Load all simulations
    simulations = []
    print("\nLoading simulations...")
    for case in os.listdir(os.path.join('data', 'real')):
        # Skip .DS_Store and other hidden files
        if case.startswith('.'):
            continue
        try:
            simulation = SimulationRun(case)
            simulations.append(simulation)
            print(f"Loaded simulation: {case}")
        except Exception as e:
            print(f"Failed to load simulation {case}: {str(e)}")
            continue

    print(f"\nTotal simulations loaded: {len(simulations)}")

    # Filter valid simulations (100 passengers)
    valid_simulations = list(filter(lambda x: x.numPassengers == 100, simulations))
    print(f"\nValid simulations after filtering: {len(valid_simulations)}")
    
    if len(valid_simulations) == 0:
        print("\nNo valid simulations found! Check the following:")
        print("1. Are there any simulations in data/real/ directory?")
        print("2. Do the simulations have numPassengers=100?")
        return

    # Filter simulations for graphs 1-3 (smart scheduling, capacity 3)
    smart_cap3_sims = [x for x in valid_simulations if x.useSmartScheduler and x.trikeCapacity == 3]
    
    # Create figure 1: Number of tricycles vs Average Passenger Waiting Time
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    x_values = [x.numTrikes for x in smart_cap3_sims]
    y_values = [sum([p["waitingTimeSeconds"] for p in x.passengers])/len(x.passengers) for x in smart_cap3_sims]
    sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values}), 
                ci=None, ax=ax1)
    ax1.set_xlabel("Number of Tricycles")
    ax1.set_ylabel("Average Passenger Waiting Time (s)")
    ax1.set_title("Effect of Number of Tricycles on Average Passenger Waiting Time")
    ax1.grid(True)
    plt.savefig(f'figures/waiting_time_tricycles_{timestamp}.png', bbox_inches='tight')
    plt.close()

    # Create figure 2: Number of tricycles vs Average Passenger Traveling Time
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    x_values = [x.numTrikes for x in smart_cap3_sims]
    y_values = [sum([p["travelingTimeSeconds"] for p in x.passengers])/len(x.passengers) for x in smart_cap3_sims]
    sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values}), 
                ci=None, ax=ax2)
    ax2.set_xlabel("Number of Tricycles")
    ax2.set_ylabel("Average Passenger Traveling Time (s)")
    ax2.set_title("Effect of Number of Tricycles on Average Passenger Traveling Time")
    ax2.grid(True)
    plt.savefig(f'figures/traveling_time_tricycles_{timestamp}.png', bbox_inches='tight')
    plt.close()

    # Create figure 3: Number of tricycles vs Tricycle Productive Time
    fig3, ax3 = plt.subplots(figsize=(10, 6))
    x_values = [x.numTrikes for x in smart_cap3_sims]
    y_values = [sum([t["productiveTravelTimeSeconds"]/t["totalTimeSeconds"] for t in x.trikes])/len(x.trikes) for x in smart_cap3_sims]
    sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values}), 
                ci=None, ax=ax3)
    ax3.set_xlabel("Number of Tricycles")
    ax3.set_ylabel("Average Tricycle Productive Time (%)")
    ax3.set_title("Effect of Number of Tricycles on Average Tricycle Productive Time")
    ax3.grid(True)
    plt.savefig(f'figures/productive_time_tricycles_{timestamp}.png', bbox_inches='tight')
    plt.close()

    # Create figure 4: FIFO vs Optimized Scheduling
    fig4, ax4 = plt.subplots(figsize=(10, 6))
    # Smart scheduling (capacity 3)
    smart_sims = [x for x in valid_simulations if x.useSmartScheduler and x.trikeCapacity == 3]
    x_smart = [x.numTrikes for x in smart_sims]
    y_smart = [sum([p["travelingTimeSeconds"] for p in x.passengers])/len(x.passengers) for x in smart_sims]
    sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_smart, 'y': y_smart}), 
                ci=None, ax=ax4, label="Optimized Scheduling")
    
    # FIFO scheduling (capacity 3)
    fifo_sims = [x for x in valid_simulations if not x.useSmartScheduler and x.trikeCapacity == 3]
    x_fifo = [x.numTrikes for x in fifo_sims]
    y_fifo = [sum([p["travelingTimeSeconds"] for p in x.passengers])/len(x.passengers) for x in fifo_sims]
    sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_fifo, 'y': y_fifo}), 
                ci=None, ax=ax4, label="FIFO Scheduling")
    
    ax4.set_xlabel("Number of Tricycles")
    ax4.set_ylabel("Average Passenger Traveling Time (s)")
    ax4.set_title("Comparison of FIFO vs Optimized Scheduling")
    ax4.legend()
    ax4.grid(True)
    plt.savefig(f'figures/scheduling_comparison_{timestamp}.png', bbox_inches='tight')
    plt.close()

    # Create figure 5: Tricycle Capacity vs Passenger Waiting Time
    fig5, ax5 = plt.subplots(figsize=(10, 6))
    x_values = [x.trikeCapacity for x in valid_simulations if x.useSmartScheduler]
    y_values = [sum([p["waitingTimeSeconds"] for p in x.passengers])/len(x.passengers) for x in valid_simulations if x.useSmartScheduler]
    sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values}), 
                ci=None, ax=ax5)
    ax5.set_xlabel("Tricycle Capacity")
    ax5.set_ylabel("Average Passenger Waiting Time (s)")
    ax5.set_title("Effect of Tricycle Capacity on Average Passenger Waiting Time")
    ax5.grid(True)
    plt.savefig(f'figures/waiting_time_capacity_{timestamp}.png', bbox_inches='tight')
    plt.close()

    # Create figure 6: Tricycle Capacity vs Passenger Traveling Time
    fig6, ax6 = plt.subplots(figsize=(10, 6))
    x_values = [x.trikeCapacity for x in valid_simulations if x.useSmartScheduler]
    y_values = [sum([p["travelingTimeSeconds"] for p in x.passengers])/len(x.passengers) for x in valid_simulations if x.useSmartScheduler]
    sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values}), 
                ci=None, ax=ax6)
    ax6.set_xlabel("Tricycle Capacity")
    ax6.set_ylabel("Average Passenger Traveling Time (s)")
    ax6.set_title("Effect of Tricycle Capacity on Average Passenger Traveling Time")
    ax6.grid(True)
    plt.savefig(f'figures/traveling_time_capacity_{timestamp}.png', bbox_inches='tight')
    plt.close()

    # Create figure 7: Tricycle Capacity vs Productive Time
    fig7, ax7 = plt.subplots(figsize=(10, 6))
    x_values = [x.trikeCapacity for x in valid_simulations if x.useSmartScheduler]
    y_values = [sum([t["productiveTravelTimeSeconds"]/t["totalTimeSeconds"] for t in x.trikes])/len(x.trikes) for x in valid_simulations if x.useSmartScheduler]
    sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values}), 
                ci=None, ax=ax7)
    ax7.set_xlabel("Tricycle Capacity")
    ax7.set_ylabel("Average Tricycle Productive Time (%)")
    ax7.set_title("Effect of Tricycle Capacity on Average Tricycle Productive Time")
    ax7.grid(True)
    plt.savefig(f'figures/productive_time_capacity_{timestamp}.png', bbox_inches='tight')
    plt.close()

    print(f"\nAll figures have been generated with timestamp {timestamp} in the 'figures' directory")

if __name__ == '__main__':
    main() 