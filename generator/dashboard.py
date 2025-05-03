import os
import json
import math
import scipy
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

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
                # st.write(data)
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
            with open(os.path.join('data', 'real', self.name, f'passenger_{i}.json')) as f:
                data = json.load(f)
                if data["offloadTime"] == -1:
                    continue
                passenger = {
                    "waitingTime": data["deathTime"]-data["createTime"],
                    "travelingTime": data["offloadTime"]-data["deathTime"],
                    "waitingTimeSeconds": (data["deathTime"]-data["createTime"]),
                    "travelingTimeSeconds": (data["offloadTime"]-data["deathTime"])
                }
                self.passengers.append(passenger)

    def __str__(self):
        return f'<{self.seed} | Trikes: {self.numTrikes}, Terminals: {self.numTerminals}, Passengers: {self.numPassengers}>'

st.header("Simulation Analysis")

simulations: list[SimulationRun] = []
for case in os.listdir(os.path.join('data', 'real')):
    try:
        simulation = SimulationRun(case)
        simulations.append(simulation)
        # st.write(case)
    except Exception as e:
        # st.exception(e)
        pass

simulations = sorted(simulations, key=lambda x: (x.numTrikes, x.numPassengers, x.name), reverse=True)

st.header("Summary")

# scatter plot for overall progressions
valid_simulations = list(filter(lambda x : x.useSmartScheduler and x.trikeCapacity == 3 and x.numPassengers == 100, simulations))
x_values = [x.numTrikes for x in valid_simulations]
y_values_trike_productive = [sum([x["productiveTravelTimeSeconds"]/x["totalTimeSeconds"] for x in y.trikes])/len(y.trikes) for y in valid_simulations]
y_values_pass_wait = [sum([x["waitingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations]
y_values_pass_travel = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations]

# plt.scatter(x_values, y_values_trike_productive)
fig, axs0 = plt.subplots(nrows=1)
p = sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values_pass_wait}), ci=None, ax=axs0, logx=True)
values_left = [sum([x["waitingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.numTrikes == 3]
values_right = [sum([x["waitingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.numTrikes == 15]
values_left_1 = [sum([x["waitingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.numTrikes == 6]
values_right_1 = [sum([x["waitingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.numTrikes == 12]
st.write(f'Average: {sum(values_left)/(60*len(values_left))}, {sum(values_right)/(60*len(values_right))}')
st.write(f'Average: {sum(values_left_1)/(60*len(values_left))}, {sum(values_right_1)/(60*len(values_right))}')
st.write(f'Trend: {p.get_lines()[0].get_ydata()[0]/60}, {p.get_lines()[0].get_ydata()[-1]/60}')

# slope, intercept, r, p, sterr = scipy.stats.linregress(x=p.get_lines()[0].get_xdata(),
#                                                        y=p.get_lines()[0].get_ydata())
# axs[0].scatter(x_values, y_values_pass_wait, label="Ave Passenger Waiting Time")

axs0.set_xlabel("Number of Tricycles")
axs0.set_ylabel("Average Passenger Waiting Time (s)")
axs0.set_title("Relationship between the number of tricycles and average passenger waiting time")
axs0.legend()
axs0.grid(True)

st.pyplot(fig)
plt.savefig('figures/fig1.png', bbox_inches='tight')

fig, axs1 = plt.subplots(nrows=1)
p = sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values_pass_travel}), ci=None, ax=axs1)
values_left = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.numTrikes == 3]
values_right = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.numTrikes == 15]
st.write(f'Average: {sum(values_left)/(60*len(values_left))}, {sum(values_right)/(60*len(values_right))}')
st.write(f'Trend: {p.get_lines()[0].get_ydata()[0]/60}, {p.get_lines()[0].get_ydata()[-1]/60}')
# axs[1].scatter(x_values, y_values_pass_travel, label="Ave Passenger Traveling Time")

axs1.set_xlabel("Number of Tricycles")
axs1.set_ylabel("Average Passenger Traveling Time (s)")
axs1.set_title("Relationship between the number of tricycles and average passenger traveling time")
axs1.legend()
axs1.grid(True)

st.pyplot(fig)
plt.savefig('figures/fig2.png', bbox_inches='tight')

fig, axs2 = plt.subplots(nrows=1)
p = sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values_trike_productive}), ci=None, ax=axs2)
values_left = [sum([x["productiveTravelTimeSeconds"]/x["totalTimeSeconds"] for x in y.trikes])/len(y.trikes) for y in valid_simulations if y.numTrikes == 3]
values_right = [sum([x["productiveTravelTimeSeconds"]/x["totalTimeSeconds"] for x in y.trikes])/len(y.trikes) for y in valid_simulations if y.numTrikes == 15]
st.write(f'Average: {sum(values_left)/(len(values_left))}, {sum(values_right)/(len(values_right))}')
st.write(f'Trend: {p.get_lines()[0].get_ydata()[0]}, {p.get_lines()[0].get_ydata()[-1]}')
# axs[2].scatter(x_values, y_values_trike_productive, label="Ave Tricycle Productive Time")
axs2.set_xlabel("Number of Tricycles")
axs2.set_ylabel("Average Tricycles Productive Time (%)")
axs2.set_title("Relationship between the number of tricycles and average tricycle productive time")
axs2.legend()
axs2.grid(True)

st.pyplot(fig)
plt.savefig('figures/fig3.png', bbox_inches='tight')

st.header("Scheduling")
valid_simulations = list(filter(lambda x: x.numPassengers == 100 and x.trikeCapacity == 3, simulations))
x_values_naive = [x.numTrikes for x in valid_simulations if not x.useSmartScheduler]
x_values_smart = [x.numTrikes for x in valid_simulations if x.useSmartScheduler]
y_values_pass_naive = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if not y.useSmartScheduler]
y_values_pass_smart = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.useSmartScheduler]

# plt.scatter(x_values, y_values_trike_productive)
figSched, axsSched = plt.subplots(nrows=1)
p = sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values_naive, 'y': y_values_pass_naive}), ci=None, ax=axsSched, label="FIFO")
values_left = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.numTrikes == 3 and not y.useSmartScheduler]
values_right = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.numTrikes == 15 and not y.useSmartScheduler]
st.write(f'Average: {sum(values_left)/(60*len(values_left))}, {sum(values_right)/(60*len(values_right))}')
st.write(f'Trend: {p.get_lines()[0].get_ydata()[0]/60}, {p.get_lines()[0].get_ydata()[-1]/60}')
p = sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values_smart, 'y': y_values_pass_smart}), ci=None, ax=axsSched, label="Optimized Scheduling")
values_left = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.numTrikes == 3 and y.useSmartScheduler]
values_right = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.numTrikes == 15 and y.useSmartScheduler]
st.write(f'Average: {sum(values_left)/(60*len(values_left))}, {sum(values_right)/(60*len(values_right))}')
st.write(f'Trend: {p.get_lines()[0].get_ydata()[0]/60}, {p.get_lines()[0].get_ydata()[-1]/60}')
# axsSched.scatter(x_values_naive, y_values_pass_naive, label="Naive Scheduling")
# axsSched.scatter(x_values_smart, y_values_pass_smart, label="Optimized Scheduling")

axsSched.set_xlabel("Number of Tricycles")
axsSched.set_ylabel("Average Passenger Traveling Time (s)")
axsSched.set_title("Effect of using Optimized Scheduling on Average Passenger Traveling Time")
axsSched.legend()
axsSched.grid(True)

st.pyplot(figSched)
plt.savefig('figures/fig4.png', bbox_inches='tight')

st.header("Trike Capacity")
valid_simulations = list(filter(lambda x: x.numPassengers == 100 and x.useSmartScheduler, simulations))
x_values = [x.trikeCapacity for x in valid_simulations]
y_values_trike_productive = [sum([x["productiveTravelTimeSeconds"]/x["totalTimeSeconds"] for x in y.trikes])/len(y.trikes) for y in valid_simulations]
y_values_pass_wait = [sum([x["waitingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations]
y_values_pass_travel = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations]

# plt.scatter(x_values, y_values_trike_productive)
fig, axs0 = plt.subplots()
p = sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values_pass_wait}), ci=None, ax=axs0)
values_left = [sum([x["waitingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.trikeCapacity == 3]
values_right = [sum([x["waitingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.trikeCapacity == 6]
st.write(f'Average: {sum(values_left)/(60*len(values_left))}, {sum(values_right)/(60*len(values_right))}')
st.write(f'Trend: {p.get_lines()[0].get_ydata()[0]/60}, {p.get_lines()[0].get_ydata()[-1]/60}')
# axs[0].scatter(x_values, y_values_pass_wait, label="Ave Passenger Waiting Time")

axs0.set_xlabel("Tricycle Capacity (number of passengers)")
axs0.set_ylabel("Average Passenger Waiting Time (s)")
axs0.set_title("Relationship between tricycle capacity and average passenger waiting time")
axs0.legend()
axs0.grid(True)

st.pyplot(fig)
plt.savefig('figures/fig5.png', bbox_inches='tight')

fig, axs1 = plt.subplots()
p = sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values_pass_travel}), ci=None, ax=axs1)
values_left = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.trikeCapacity == 3]
values_right = [sum([x["travelingTimeSeconds"] for x in y.passengers])/len(y.passengers) for y in valid_simulations if y.trikeCapacity == 6]
st.write(f'Average: {sum(values_left)/(60*len(values_left))}, {sum(values_right)/(60*len(values_right))}')
st.write(f'Trend: {p.get_lines()[0].get_ydata()[0]/60}, {p.get_lines()[0].get_ydata()[-1]/60}')
# axs[1].scatter(x_values, y_values_pass_travel, label="Ave Passenger Traveling Time")

axs1.set_xlabel("Tricycle Capacity (number of passengers)")
axs1.set_ylabel("Average Passenger Traveling Time (s)")
axs1.set_title("Relationship between tricycle capacity and average passenger waiting time")
axs1.legend()
axs1.grid(True)

st.pyplot(fig)
plt.savefig('figures/fig6.png', bbox_inches='tight')

fig, axs2 = plt.subplots()
p = sns.regplot(x='x', y='y', data=pd.DataFrame({'x': x_values, 'y': y_values_trike_productive}), ci=None, ax=axs2)
values_left = [sum([x["productiveTravelTimeSeconds"]/x["totalTimeSeconds"] for x in y.trikes])/len(y.trikes) for y in valid_simulations if y.numTrikes == 3]
values_right = [sum([x["productiveTravelTimeSeconds"]/x["totalTimeSeconds"] for x in y.trikes])/len(y.trikes) for y in valid_simulations if y.numTrikes == 15]
st.write(f'Average: {sum(values_left)/(len(values_left))}, {sum(values_right)/(len(values_right))}')
st.write(f'Trend: {p.get_lines()[0].get_ydata()[0]}, {p.get_lines()[0].get_ydata()[-1]}')
# axs[2].scatter(x_values, y_values_trike_productive, label="Ave Tricycle Productive Time")

axs2.set_xlabel("Tricycle Capacity (number of passengers)")
axs2.set_ylabel("Average Tricycle Productive Time (%)")
axs2.set_title("Relationship between tricycle capacity and average tricycle productive time")
axs2.legend()
axs2.grid(True)

st.pyplot(fig)
plt.savefig('figures/fig7.png', bbox_inches='tight')

showSimulation = st.selectbox("Choose a simulation to view", simulations)

if showSimulation:
    metaTab, trikeTab, passengerTab = st.tabs(["View Summary", "View Tricycle Stats", "View Passenger Stats"])

    with metaTab:
        st.header("Metadata")
        with open(os.path.join('data', 'real', showSimulation.name, 'metadata.json')) as f:
            metadata = json.load(f)
        st.write(metadata)

        st.header("Tricycles")
        trike_headers = ["ProductiveTravel", "UnproductiveTravel", "IdleWaiting"]
        trike_values = [
            sum([x["productiveTravelTimeSeconds"]/x["totalTimeSeconds"] for x in showSimulation.trikes]),
            sum([x["unproductiveTravelTimeSeconds"]/x["totalTimeSeconds"] for x in showSimulation.trikes]),
            sum([x["waitingTimeSeconds"]/x["totalTimeSeconds"] for x in showSimulation.trikes]),
        ]

        fig, ax = plt.subplots()
        wedges, texts, autotexts = ax.pie(trike_values, autopct='%1.1f%%', startangle=90)
        ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        ax.legend(wedges, trike_headers, title="Category", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))

        st.pyplot(fig)

        st.header("Passengers")
        pass_waiting_time = [x["waitingTime"] for x in showSimulation.passengers]
        pass_traveling_time = [x["travelingTime"] for x in showSimulation.passengers]
        
        fig_pass, axs = plt.subplots(ncols=2)
        axs[0].hist(pass_waiting_time, bins=20)
        axs[0].set_title("Passenger Waiting Times")
        axs[0].set_xlabel("Waiting time")
        axs[0].set_ylabel("Frequency")

        axs[1].hist(pass_traveling_time, bins=20)
        axs[1].set_title("Passenger Traveling Times")
        axs[1].set_xlabel("Traveling time")
        axs[1].set_ylabel("Frequency")
        st.pyplot(fig_pass)

    with trikeTab:
        try:
            st.header("Tricycles")
            headers = ["ProductiveTravel", "UnproductiveTravel", "IdleWaiting"]
            fig, axs = plt.subplots(ncols=1, nrows=math.ceil(showSimulation.numTrikes/1), figsize=(7,30))

            for ax, trike in zip(axs, showSimulation.trikes):
                values = [
                    trike["productiveTravelTimeSeconds"], 
                    trike["unproductiveTravelTimeSeconds"],
                    trike["waitingTimeSeconds"]
                ]
                wedges, texts, autotexts = ax.pie(values, autopct='%1.1f%%', startangle=90)
                ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
                ax.legend(wedges, headers, title="Category", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))

            # Display the pie chart
            st.pyplot(fig)
        except Exception:
            pass

    with passengerTab:
        try:
            st.header("Passengers")
            waiting_times = [passenger["waitingTime"] for passenger in showSimulation.passengers]
            traveling_times = [passenger["travelingTime"] for passenger in showSimulation.passengers]

            fig, ax = plt.subplots(figsize=(10, 8))

            # Create the bar positions
            indices = np.arange(len(showSimulation.passengers))

            # Plot the stacked bars
            ax.barh(indices, waiting_times, color='skyblue', label='WaitingTime')
            ax.barh(indices, traveling_times, left=waiting_times, color='lightgreen', label='TravelingTime')

            # Set labels and legend
            ax.set_xlabel('Time')
            ax.set_ylabel('Passengers')
            ax.set_title('Waiting and Traveling Times of Passengers')
            ax.legend()

            # Set x-ticks to show passenger numbers

            # Display the plot in Streamlit
            st.pyplot(fig)
        except Exception as e:
            st.exception(e)