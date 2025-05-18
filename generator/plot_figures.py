import os
import json
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

class SimulationRun:
    def __init__(self, name):
        self.name = name
        numTrikes, numTerminals, numPassengers, seed = name.split('-')
        self.numTrikes = int(numTrikes)
        self.numTerminals = int(numTerminals)
        self.numPassengers = int(numPassengers)
        self.seed = seed

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

    # Sort simulations
    simulations = sorted(simulations, key=lambda x: (x.numTrikes, x.numPassengers, x.name), reverse=True)

    # Filter valid simulations (100 passengers, any scheduling type)
    valid_simulations = list(filter(lambda x: x.numPassengers == 100, simulations))
    print(f"\nValid simulations after filtering: {len(valid_simulations)}")
    
    if len(valid_simulations) == 0:
        print("\nNo valid simulations found! Check the following:")
        print("1. Are there any simulations in data/real/ directory?")
        print("2. Do the simulations have numPassengers=100?")
        return

    # Prepare data for scheduling analysis (fig4)
    x_values_naive = [x.numTrikes for x in valid_simulations if not x.useSmartScheduler]
    x_values_smart = [x.numTrikes for x in valid_simulations if x.useSmartScheduler]
    y_values_pass_naive = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if not y.useSmartScheduler]
    y_values_pass_smart = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.useSmartScheduler]

    print("\nData points for scheduling analysis:")
    print(f"FIFO - Number of tricycles: {x_values_naive}")
    print(f"FIFO - Average traveling times: {y_values_pass_naive}")
    print(f"Smart - Number of tricycles: {x_values_smart}")
    print(f"Smart - Average traveling times: {y_values_pass_smart}")

    # Create figure 4: Scheduling Analysis
    fig4, ax4 = plt.subplots(figsize=(10, 6))
    if x_values_naive and y_values_pass_naive:  # Only plot FIFO if we have data
        p4_naive = sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values_naive, 'y': y_values_pass_naive}), 
                              ci=None, ax=ax4, label="FIFO")
    if x_values_smart and y_values_pass_smart:  # Only plot Smart if we have data
        p4_smart = sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values_smart, 'y': y_values_pass_smart}), 
                              ci=None, ax=ax4, label="Optimized Scheduling")
    ax4.set_xlabel("Number of Tricycles")
    ax4.set_ylabel("Average Passenger Traveling Time (s)")
    ax4.set_title("Effect of using Optimized Scheduling on Average Passenger Traveling Time")
    ax4.legend()
    ax4.grid(True)
    plt.savefig('figures/roaming_fig4.png', bbox_inches='tight')
    plt.close()

    # Prepare data for other metrics (only for smart scheduling cases)
    smart_simulations = list(filter(lambda x: x.useSmartScheduler, valid_simulations))
    x_values = [x.numTrikes for x in smart_simulations]
    y_values_trike_productive = [sum([x["productiveTravelTimeSeconds"]/x["totalTimeSeconds"] for x in y.trikes])/len(y.trikes) for y in smart_simulations]
    y_values_pass_wait = [sum([x["waitingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in smart_simulations]
    y_values_pass_travel = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in smart_simulations]

    print("\nData points for smart scheduling metrics:")
    print(f"Number of tricycles: {x_values}")
    print(f"Average waiting times: {y_values_pass_wait}")
    print(f"Average traveling times: {y_values_pass_travel}")
    print(f"Average productive times: {y_values_trike_productive}")

    if not y_values_pass_wait:
        print("\nNo valid data points to plot! Check if any passengers completed their trips.")
        return

    # Create figure 1: Average Passenger Waiting Time
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    if x_values_naive and y_values_pass_naive:
        p1_naive = sns.regplot(x='x', y='y', 
            data=pd.DataFrame({
                'x': x_values_naive, 
                'y': [sum([x["waitingTimeSeconds"] for x in y.passengers])/len(y.passengers) 
                      for y in valid_simulations if not y.useSmartScheduler]
            }), 
            ci=None, ax=ax1, label="FIFO", logx=True)
    if x_values_smart and y_values_pass_smart:
        p1_smart = sns.regplot(x='x', y='y', 
            data=pd.DataFrame({
                'x': x_values_smart, 
                'y': [sum([x["waitingTimeSeconds"] for x in y.passengers])/len(y.passengers) 
                      for y in valid_simulations if y.useSmartScheduler]
            }), 
            ci=None, ax=ax1, label="Optimized Scheduling", logx=True)
    ax1.set_xlabel("Number of Tricycles")
    ax1.set_ylabel("Average Passenger Waiting Time (s)")
    ax1.set_title("Effect of Scheduling on Average Passenger Waiting Time")
    ax1.legend()
    ax1.grid(True)
    plt.savefig('figures/roaming_fig1.png', bbox_inches='tight')
    plt.close()

    # Create figure 2: Average Passenger Traveling Time
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    if x_values_naive and y_values_pass_naive:
        p2_naive = sns.regplot(x='x', y='y', 
            data=pd.DataFrame({
                'x': x_values_naive, 
                'y': [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) 
                      for y in valid_simulations if not y.useSmartScheduler]
            }), 
            ci=None, ax=ax2, label="FIFO", logx=True)
    if x_values_smart and y_values_pass_smart:
        p2_smart = sns.regplot(x='x', y='y', 
            data=pd.DataFrame({
                'x': x_values_smart, 
                'y': [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) 
                      for y in valid_simulations if y.useSmartScheduler]
            }), 
            ci=None, ax=ax2, label="Optimized Scheduling", logx=True)
    ax2.set_xlabel("Number of Tricycles")
    ax2.set_ylabel("Average Passenger Traveling Time (s)")
    ax2.set_title("Effect of Scheduling on Average Passenger Traveling Time")
    ax2.legend()
    ax2.grid(True)
    plt.savefig('figures/roaming_fig2.png', bbox_inches='tight')
    plt.close()

    # Create figure 3: Average Tricycle Productive Time
    fig3, ax3 = plt.subplots(figsize=(10, 6))
    if x_values_naive and y_values_pass_naive:
        p3_naive = sns.regplot(x='x', y='y', 
            data=pd.DataFrame({
                'x': x_values_naive, 
                'y': [sum([x["productiveTravelTimeSeconds"]/x["totalTimeSeconds"] for x in y.trikes])/len(y.trikes) 
                      for y in valid_simulations if not y.useSmartScheduler]
            }), 
            ci=None, ax=ax3, label="FIFO", logx=True)
    if x_values_smart and y_values_pass_smart:
        p3_smart = sns.regplot(x='x', y='y', 
            data=pd.DataFrame({
                'x': x_values_smart, 
                'y': [sum([x["productiveTravelTimeSeconds"]/x["totalTimeSeconds"] for x in y.trikes])/len(y.trikes) 
                      for y in valid_simulations if y.useSmartScheduler]
            }), 
            ci=None, ax=ax3, label="Optimized Scheduling", logx=True)
    ax3.set_xlabel("Number of Tricycles")
    ax3.set_ylabel("Average Tricycle Productive Time (%)")
    ax3.set_title("Effect of Scheduling on Average Tricycle Productive Time")
    ax3.legend()
    ax3.grid(True)
    plt.savefig('figures/roaming_fig3.png', bbox_inches='tight')
    plt.close()

    # Prepare data for scheduling analysis (fig4)
    x_values_naive = [x.numTrikes for x in valid_simulations if not x.useSmartScheduler]
    x_values_smart = [x.numTrikes for x in valid_simulations if x.useSmartScheduler]
    y_values_pass_naive = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if not y.useSmartScheduler]
    y_values_pass_smart = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.useSmartScheduler]

    print("\nData points for scheduling analysis:")
    print(f"FIFO - Number of tricycles: {x_values_naive}")
    print(f"FIFO - Average traveling times: {y_values_pass_naive}")
    print(f"Smart - Number of tricycles: {x_values_smart}")
    print(f"Smart - Average traveling times: {y_values_pass_smart}")

    # # Create figure 4: Scheduling Analysis
    fig4, ax4 = plt.subplots(figsize=(10, 6))
    p4_naive = sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values_naive, 'y': y_values_pass_naive}), 
                          ci=None, ax=ax4, label="FIFO")
    p4_smart = sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values_smart, 'y': y_values_pass_smart}), 
                          ci=None, ax=ax4, label="Optimized Scheduling")
    ax4.set_xlabel("Number of Tricycles")
    ax4.set_ylabel("Average Passenger Traveling Time (s)")
    ax4.set_title("Effect of using Optimized Scheduling on Average Passenger Traveling Time")
    ax4.legend()
    ax4.grid(True)
    plt.savefig('figures/roaming_fig4.png', bbox_inches='tight')
    plt.close()

    # # Calculate metrics for each capacity
    # capacity_metrics = {}
    # for capacity, sims in capacity_groups.items():
    #     capacity_metrics[capacity] = {
    #         'waiting_time': [sum([x["waitingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in sims],
    #         'traveling_time': [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in sims],
    #         'productive_time': [sum([x["productiveTravelTimeSeconds"]/x["totalTimeSeconds"] for x in y.trikes])/len(y.trikes) for y in sims]
    #     }

    # # Create figure 5: Average Passenger Waiting Time by Capacity
    # fig5, ax5 = plt.subplots()
    # p = sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values_pass_wait}), ci=None, ax=ax5)
    # values_left = [sum([x["waitingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.trikeCapacity == 3]
    # values_right = [sum([x["waitingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.trikeCapacity == 6]
    # print(f'Average: {sum(values_left)/(60*len(values_left))}, {sum(values_right)/(60*len(values_right))}')
    # print(f'Trend: {p.get_lines()[0].get_ydata()[0]/60}, {p.get_lines()[0].get_ydata()[-1]/60}')

    # ax5.set_xlabel("Tricycle Capacity (number of passengers)")
    # ax5.set_ylabel("Average Passenger Waiting Time (s)")
    # ax5.set_title("Relationship between tricycle capacity and average passenger waiting time")
    # ax5.legend()
    # ax5.grid(True)
    # plt.savefig('figures/roaming_fig5.png', bbox_inches='tight')
    # plt.close()

    # # Create figure 6: Average Passenger Traveling Time by Capacity
    # fig6, ax6 = plt.subplots()
    # p = sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values_pass_travel}), ci=None, ax=ax6)
    # values_left = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.trikeCapacity == 3]
    # values_right = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.trikeCapacity == 6]
    # print(f'Average: {sum(values_left)/(60*len(values_left))}, {sum(values_right)/(60*len(values_right))}')
    # print(f'Trend: {p.get_lines()[0].get_ydata()[0]/60}, {p.get_lines()[0].get_ydata()[-1]/60}')

    # ax6.set_xlabel("Tricycle Capacity (number of passengers)")
    # ax6.set_ylabel("Average Passenger Traveling Time (s)")
    # ax6.set_title("Relationship between tricycle capacity and average passenger waiting time")
    # ax6.legend()
    # ax6.grid(True)
    # plt.savefig('figures/roaming_fig6.png', bbox_inches='tight')
    # plt.close()

    # # Create figure 7: Average Tricycle Productive Time by Capacity
    # fig7, ax7 = plt.subplots()
    # p = sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values_trike_productive}), ci=None, ax=ax7)
    # values_left = [sum([x["productiveTravelTimeSeconds"]/x["totalTimeSeconds"] for x in y.trikes])/len(y.trikes) for y in valid_simulations if y.numTrikes == 3]
    # values_right = [sum([x["productiveTravelTimeSeconds"]/x["totalTimeSeconds"] for x in y.trikes])/len(y.trikes) for y in valid_simulations if y.numTrikes == 15]
    # print(f'Average: {sum(values_left)/(len(values_left))}, {sum(values_right)/(len(values_right))}')
    # print(f'Trend: {p.get_lines()[0].get_ydata()[0]}, {p.get_lines()[0].get_ydata()[-1]}')

    # ax7.set_xlabel("Tricycle Capacity (number of passengers)")
    # ax7.set_ylabel("Average Tricycle Productive Time (%)")
    # ax7.set_title("Relationship between tricycle capacity and average tricycle productive time")
    # ax7.legend()
    # ax7.grid(True)
    # plt.savefig('figures/roaming_fig7.png', bbox_inches='tight')
    # plt.close()

    # print("\nCapacity analysis graphs have been generated and saved in the 'figures' directory")

if __name__ == '__main__':
    main() 