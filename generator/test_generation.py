import os
import sys
import time
import json
from datetime import datetime

# Add the generator directory to Python path
generator_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, generator_dir)

from scenarios.real import Simulator
import config

def run_simulation(num_trikes, use_smart_scheduler=True, trike_capacity=3):
    """
    Run a single simulation with the given parameters.
    
    Args:
        num_trikes (int): Number of tricycles to simulate
        use_smart_scheduler (bool): Whether to use smart scheduling or FIFO
        trike_capacity (int): Capacity of each tricycle
    Returns:
        dict: Simulation results
    """
    # Common parameters
    params = {
        'totalTrikes': num_trikes,
        'totalTerminals': 2,
        'totalPassengers': 100,
        'useSmartScheduler': use_smart_scheduler,
        'trikeCapacity': trike_capacity,
        'isRealistic': True,
        'useFixedHotspots': True,
        'useFixedTerminals': False,
        'roadPassengerChance': 1.0,
        'roamingTrikeChance': 1.0
    }
    
    # Create simulator instance
    simulator = Simulator(**params)
    
    # Run simulation
    print(f"\nRunning simulation with {num_trikes} tricycles (capacity: {trike_capacity})")
    start_time = time.time()
    results = simulator.run(maxTime=10000, fixedHotspots=config.MAGIN_HOTSPOTS, fixedTerminals=config.MAGIN_TERMINALS)
    end_time = time.time()
    
    # Add execution time to results
    results['execution_time_seconds'] = end_time - start_time
    
    print(f"Simulation completed in {results['execution_time_seconds']:.2f} seconds")
    return results

def main():
    # Create data directory if it doesn't exist
    data_dir = os.path.join('data', 'real')
    os.makedirs(data_dir, exist_ok=True)

    # Test parameters
    tricycle_counts = [3, 6, 9, 12, 15]
    
    # Store all results
    all_results = {
        'timestamp': datetime.now().isoformat(),
        'simulations': []
    }
    
    # # Run roaming simulations with smart scheduling
    # print("\n=== Running Roaming Simulations with Smart Scheduling ===")
    # for num_trikes in tricycle_counts:
    #     results = run_simulation(num_trikes, use_smart_scheduler=True, trike_capacity=3)
    #     all_results['simulations'].append(results)
    
    # Run simulations with FIFO scheduling
    print("\n=== Running Simulations with FIFO Scheduling ===")
    for num_trikes in tricycle_counts:
        results = run_simulation(num_trikes, use_smart_scheduler=False, trike_capacity=3)
        all_results['simulations'].append(results)

    # Run simulations with different tricycle capacities
    # print("\n=== Running Simulations with Different Tricycle Capacities ===")
    # tricycle_capacities = [4, 5, 6]  # Test different capacity values
    # for capacity in tricycle_capacities:
    #     for num_trikes in tricycle_counts:
    #         results = run_simulation(num_trikes, use_smart_scheduler=True, trike_capacity=capacity)
    #         all_results['simulations'].append(results)

if __name__ == '__main__':
    main() 