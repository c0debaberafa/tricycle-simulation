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

def run_simulation(num_trikes, use_smart_scheduler=True, trike_capacity=3, seed=None):
    """
    Run a single simulation with the given parameters.
    
    Args:
        num_trikes (int): Number of tricycles to simulate
        use_smart_scheduler (bool): Whether to use smart scheduling or FIFO
        trike_capacity (int): Capacity of each tricycle
        seed (str): Seed string for reproducibility
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
        'roamingTrikeChance': 1.0,
        'seed': seed
    }
    
    # Create simulator instance
    simulator = Simulator(**params)
    
    # Run simulation
    print(f"\nRunning simulation with {num_trikes} tricycles (capacity: {trike_capacity}, seed: {seed})")
    start_time = time.time()
    try:
        results = simulator.run(maxTime=10000, fixedHotspots=config.MAGIN_HOTSPOTS, fixedTerminals=config.MAGIN_TERMINALS)
        end_time = time.time()
        
        # Add execution time to results
        results['execution_time_seconds'] = end_time - start_time
        
        print(f"Simulation completed in {results['execution_time_seconds']:.2f} seconds")
        return results
    except Exception as e:
        print(f"Error running simulation: {str(e)}")
        return None

def main():
    # Create data directory if it doesn't exist
    data_dir = os.path.join('data', 'real')
    os.makedirs(data_dir, exist_ok=True)

    # Test parameters
    tricycle_counts = [3, 6, 9, 12, 15]
    tricycle_capacities = [3, 4, 5, 6]
    num_runs = 5  # Number of runs per parameter combination
    
    # Store all results
    all_results = {
        'timestamp': datetime.now().isoformat(),
        'simulations': []
    }
    
    # 1. Run smart scheduling tests with capacity 3 (for graphs 1-3)
    print("\n=== Running Smart Scheduling Tests (capacity 3) ===")
    for num_trikes in tricycle_counts:
        for run in range(num_runs):
            seed = f"graphdata{run}"  # Using string seeds
            results = run_simulation(num_trikes, use_smart_scheduler=True, trike_capacity=3, seed=seed)
            if results:  # Only append if simulation was successful
                all_results['simulations'].append(results)
    
    # # 2. Run FIFO scheduling tests with capacity 3 (for graph 4)
    # print("\n=== Running FIFO Scheduling Tests (capacity 3) ===")
    # for num_trikes in tricycle_counts:
    #     for run in range(num_runs):
    #         seed = f"graphdata{run}"
    #         results = run_simulation(num_trikes, use_smart_scheduler=False, trike_capacity=3, seed=seed)
    #         if results:
    #             all_results['simulations'].append(results)

    # # 3. Run capacity analysis tests (for graphs 5-7)
    # print("\n=== Running Capacity Analysis Tests ===")
    # for capacity in tricycle_capacities:
    #     for num_trikes in tricycle_counts:
    #         for run in range(num_runs):
    #             seed = f"graphdata{run}"
    #             results = run_simulation(num_trikes, use_smart_scheduler=True, trike_capacity=capacity, seed=seed)
    #             if results:
    #                 all_results['simulations'].append(results)

    print(f"\nTotal simulations completed: {len(all_results['simulations'])}")
    print("All test data has been saved to the data/real directory")

if __name__ == '__main__':
    main() 