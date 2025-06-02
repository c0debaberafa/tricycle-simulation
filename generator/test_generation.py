import os
import sys
import time
import json
from datetime import datetime
import traceback

# Add the generator directory to Python path
generator_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, generator_dir)

from scenarios.real import Simulator
import config

def save_progress(all_results, data_dir):
    """Save current progress to a temporary file"""
    temp_file = os.path.join(data_dir, 'simulation_progress.json')
    with open(temp_file, 'w') as f:
        json.dump(all_results, f, indent=2)

def load_progress(data_dir):
    """Load progress from temporary file if it exists"""
    temp_file = os.path.join(data_dir, 'simulation_progress.json')
    if os.path.exists(temp_file):
        with open(temp_file, 'r') as f:
            return json.load(f)
    return None

def get_config_key(num_trikes, use_smart_scheduler, trike_capacity, s_enqueue_radius_meters, enqueue_radius_meters, maxCycles):
    """Generate a unique key for a configuration"""
    return (num_trikes, use_smart_scheduler, trike_capacity, s_enqueue_radius_meters, enqueue_radius_meters, maxCycles)

def find_matching_simulation(all_results, config_key, seed_prefix):
    """Find a simulation that matches the given configuration and hasn't been used for this group yet"""
    used_seeds = {sim['metadata']['seed'] for sim in all_results['simulations'] if sim['metadata']['seed'].startswith(seed_prefix)}
    
    for sim in all_results['simulations']:
        sim_key = get_config_key(
            sim['metadata']['num_trikes'],
            sim['metadata']['use_smart_scheduler'],
            sim['metadata']['trike_capacity'],
            sim['metadata']['s_enqueue_radius_meters'],
            sim['metadata']['enqueue_radius_meters'],
            sim['metadata']['maxCycles']
        )
        if sim_key == config_key and sim['metadata']['seed'] not in used_seeds:
            return sim
    return None

def run_simulation(num_trikes, use_smart_scheduler=True, trike_capacity=3, seed=None, max_retries=10, max_wait_time=300, s_enqueue_radius_meters=50, enqueue_radius_meters=200, maxCycles=2):
    """
    Run a single simulation with the given parameters.
    
    Args:
        num_trikes (int): Number of tricycles to simulate
        use_smart_scheduler (bool): Whether to use smart scheduling or FIFO
        trike_capacity (int): Capacity of each tricycle
        seed (str): Seed string for reproducibility
        max_retries (int): Maximum number of retries for failed simulations
        max_wait_time (int): Maximum wait time between retries in seconds
        s_enqueue_radius_meters (float): Radius for enqueueing when tricycle is serving passengers
        enqueue_radius_meters (float): Radius for enqueueing when tricycle is not serving passengers
        maxCycles (int): Maximum number of cycles before generating new path
    Returns:
        dict: Simulation results or None if all retries failed
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
        'trikeConfig': {
            'capacity': trike_capacity,
            'speed': 5.556,  # 20 km/h in meters per second
            'scheduler': None,  # Will be set by Simulator based on useSmartScheduler
            'useMeters': True,
            'maxCycles': maxCycles,
            's_enqueue_radius_meters': s_enqueue_radius_meters,
            'enqueue_radius_meters': enqueue_radius_meters
        }
    }
    
    attempt = 0
    total_wait_time = 0
    last_error = None
    
    while attempt < max_retries:
        try:
            # Create simulator instance
            simulator = Simulator(**params)
            
            # Run simulation
            print(f"\nRunning simulation with {num_trikes} tricycles (capacity: {trike_capacity}, s_radius: {s_enqueue_radius_meters}, e_radius: {enqueue_radius_meters}, maxCycles: {maxCycles}, seed: {seed}, attempt: {attempt + 1}/{max_retries})")
            start_time = time.time()
            
            results = simulator.run(seed=seed, maxTime=15000, fixedHotspots=config.MAGIN_HOTSPOTS, fixedTerminals=config.MAGIN_TERMINALS)
            end_time = time.time()
            
            # Add execution time and metadata to results
            results['execution_time_seconds'] = end_time - start_time
            results['metadata'] = {
                'num_trikes': num_trikes,
                'use_smart_scheduler': use_smart_scheduler,
                'trike_capacity': trike_capacity,
                'seed': seed,
                'attempt': attempt + 1,
                'total_retries': attempt,
                'total_wait_time': total_wait_time,
                's_enqueue_radius_meters': s_enqueue_radius_meters,
                'enqueue_radius_meters': enqueue_radius_meters,
                'maxCycles': maxCycles
            }
            
            print(f"Simulation completed in {results['execution_time_seconds']:.2f} seconds")
            return results
            
        except Exception as e:
            last_error = e
            print(f"Error running simulation (attempt {attempt + 1}/{max_retries}): {str(e)}")
            
            # Calculate wait time with exponential backoff
            wait_time = min(5 * (2 ** attempt), max_wait_time)  # Start with 5s, double each time, but cap at max_wait_time
            total_wait_time += wait_time
            
            if "OSRM" in str(e):
                print(f"OSRM server error detected, waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                # For non-OSRM errors, wait a shorter time
                wait_time = min(wait_time / 2, 30)  # Cap at 30 seconds for non-OSRM errors
                print(f"Error detected, waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            
            attempt += 1
            continue
    
    print("All retry attempts failed")
    print("Last error:", str(last_error))
    print("Full error traceback:")
    print(traceback.format_exc())
    return None

def print_progress(group_a_completed, group_b_completed, group_c_completed, group_d_completed, 
                  completed_simulations, total_simulations, tricycle_counts, tricycle_capacities, 
                  enqueue_radii, s_enqueue_radii, num_runs):
    """Print progress update for all groups"""
    print(f"\nProgress Update:")
    print(f"Group A: {group_a_completed}/{len(tricycle_counts) * num_runs} simulations completed")
    print(f"Group B: {group_b_completed}/{len(tricycle_capacities) * num_runs} simulations completed")
    print(f"Group C: {group_c_completed}/{len(enqueue_radii) * num_runs} simulations completed")
    print(f"Group D: {group_d_completed}/{len(s_enqueue_radii) * num_runs} simulations completed")
    print(f"Overall: {completed_simulations}/{total_simulations} simulations completed ({(completed_simulations/total_simulations)*100:.1f}%)")
    print("########################################################")

def main():
    # Create data directory if it doesn't exist
    data_dir = os.path.join('data', 'real')
    os.makedirs(data_dir, exist_ok=True)

    # Test parameters for each group
    # Group A: Number of tricycles (fixed capacity=3, s_radius=50, e_radius=100, maxCycles=2)
    tricycle_counts = [3, 6, 9, 12, 15]
    
    # Group B: Tricycle capacity (fixed trikes=9, s_radius=50, e_radius=100, maxCycles=2)
    tricycle_capacities = [3, 4, 5, 6]
    
    # Group C: Enqueue radius (fixed trikes=9, capacity=3, s_radius=50, maxCycles=2)
    enqueue_radii = [50, 100, 150, 200]
    
    # Group D: Serving enqueue radius (fixed trikes=9, capacity=3, e_radius=100, maxCycles=2)
    s_enqueue_radii = [25, 50, 75, 100]
    
    num_runs = 50  # Number of runs per parameter combination
    
    # Calculate total number of simulations
    total_simulations = (
        len(tricycle_counts) * num_runs +  # Group A
        len(tricycle_capacities) * num_runs +  # Group B
        len(enqueue_radii) * num_runs +  # Group C
        len(s_enqueue_radii) * num_runs  # Group D
    )
    
    # Try to load existing progress
    all_results = load_progress(data_dir)
    if all_results is None:
        all_results = {
            'timestamp': datetime.now().isoformat(),
            'simulations': []
        }
    
    # Track completed configurations (without seeds)
    completed_configs = {
        get_config_key(
            sim['metadata']['num_trikes'],
            sim['metadata']['use_smart_scheduler'],
            sim['metadata']['trike_capacity'],
            sim['metadata']['s_enqueue_radius_meters'],
            sim['metadata']['enqueue_radius_meters'],
            sim['metadata']['maxCycles']
        )
        for sim in all_results['simulations']
    }

    # Initialize progress counters
    completed_simulations = len(all_results['simulations'])
    group_a_completed = sum(1 for sim in all_results['simulations'] if sim['metadata'].get('seed', '').startswith('groupA_'))
    group_b_completed = sum(1 for sim in all_results['simulations'] if sim['metadata'].get('seed', '').startswith('groupB_'))
    group_c_completed = sum(1 for sim in all_results['simulations'] if sim['metadata'].get('seed', '').startswith('groupC_'))
    group_d_completed = sum(1 for sim in all_results['simulations'] if sim['metadata'].get('seed', '').startswith('groupD_'))

    def update_progress():
        print_progress(group_a_completed, group_b_completed, group_c_completed, group_d_completed,
                      completed_simulations, total_simulations, tricycle_counts, tricycle_capacities,
                      enqueue_radii, s_enqueue_radii, num_runs)

    # Group A: Number of tricycles analysis
    print("\n=== Running Group A: Number of Tricycles Analysis ===")
    for num_trikes in tricycle_counts:
        for run in range(num_runs):
            seed = f"groupA_{num_trikes}_{run}"
            config_key = get_config_key(num_trikes, True, 3, 50, 100, 2)
            
            # Check if we already have this configuration
            existing_sim = find_matching_simulation(all_results, config_key, 'groupA_')
            if existing_sim:
                print(f"\nReusing existing simulation for Group A - Number of Tricycles: {num_trikes}")
                print(f"Configuration: capacity=3, s_radius=50, e_radius=100, maxCycles=2")
                # Copy the existing simulation with a new seed
                new_sim = existing_sim.copy()
                new_sim['metadata']['seed'] = seed
                all_results['simulations'].append(new_sim)
                save_progress(all_results, data_dir)
                completed_simulations += 1
                group_a_completed += 1
                update_progress()
            elif config_key not in completed_configs:
                print(f"\nTesting Group A - Number of Tricycles: {num_trikes}")
                print(f"Fixed parameters: capacity=3, s_radius=50, e_radius=100, maxCycles=2")
                results = run_simulation(
                    num_trikes,
                    use_smart_scheduler=True,
                    trike_capacity=3,
                    seed=seed,
                    s_enqueue_radius_meters=50,
                    enqueue_radius_meters=100,
                    maxCycles=2
                )
                if results:
                    all_results['simulations'].append(results)
                    completed_configs.add(config_key)
                    save_progress(all_results, data_dir)
                    completed_simulations += 1
                    group_a_completed += 1
                    update_progress()

    # Group B: Tricycle capacity analysis
    print("\n=== Running Group B: Tricycle Capacity Analysis ===")
    for capacity in tricycle_capacities:
        for run in range(num_runs):
            seed = f"groupB_{capacity}_{run}"
            config_key = get_config_key(9, True, capacity, 50, 100, 2)
            
            # Check if we already have this configuration
            existing_sim = find_matching_simulation(all_results, config_key, 'groupB_')
            if existing_sim:
                print(f"\nReusing existing simulation for Group B - Tricycle Capacity: {capacity}")
                print(f"Configuration: trikes=9, s_radius=50, e_radius=100, maxCycles=2")
                # Copy the existing simulation with a new seed
                new_sim = existing_sim.copy()
                new_sim['metadata']['seed'] = seed
                all_results['simulations'].append(new_sim)
                save_progress(all_results, data_dir)
                completed_simulations += 1
                group_b_completed += 1
                update_progress()
            elif config_key not in completed_configs:
                print(f"\nTesting Group B - Tricycle Capacity: {capacity}")
                print(f"Fixed parameters: trikes=9, s_radius=50, e_radius=100, maxCycles=2")
                results = run_simulation(
                    9,  # Fixed number of tricycles
                    use_smart_scheduler=True,
                    trike_capacity=capacity,
                    seed=seed,
                    s_enqueue_radius_meters=50,
                    enqueue_radius_meters=100,
                    maxCycles=2
                )
                if results:
                    all_results['simulations'].append(results)
                    completed_configs.add(config_key)
                    save_progress(all_results, data_dir)
                    completed_simulations += 1
                    group_b_completed += 1
                    update_progress()

    # Group C: Enqueue radius analysis
    print("\n=== Running Group C: Enqueue Radius Analysis ===")
    for radius in enqueue_radii:
        for run in range(num_runs):
            seed = f"groupC_{radius}_{run}"
            config_key = get_config_key(9, True, 3, 50, radius, 2)
            
            # Check if we already have this configuration
            existing_sim = find_matching_simulation(all_results, config_key, 'groupC_')
            if existing_sim:
                print(f"\nReusing existing simulation for Group C - Enqueue Radius: {radius} meters")
                print(f"Configuration: trikes=9, capacity=3, s_radius=50, maxCycles=2")
                # Copy the existing simulation with a new seed
                new_sim = existing_sim.copy()
                new_sim['metadata']['seed'] = seed
                all_results['simulations'].append(new_sim)
                save_progress(all_results, data_dir)
                completed_simulations += 1
                group_c_completed += 1
                update_progress()
            elif config_key not in completed_configs:
                print(f"\nTesting Group C - Enqueue Radius: {radius} meters")
                print(f"Fixed parameters: trikes=9, capacity=3, s_radius=50, maxCycles=2")
                results = run_simulation(
                    9,  # Fixed number of tricycles
                    use_smart_scheduler=True,
                    trike_capacity=3,
                    seed=seed,
                    s_enqueue_radius_meters=50,
                    enqueue_radius_meters=radius,
                    maxCycles=2
                )
                if results:
                    all_results['simulations'].append(results)
                    completed_configs.add(config_key)
                    save_progress(all_results, data_dir)
                    completed_simulations += 1
                    group_c_completed += 1
                    update_progress()

    # Group D: Serving enqueue radius analysis
    print("\n=== Running Group D: Serving Enqueue Radius Analysis ===")
    for radius in s_enqueue_radii:
        for run in range(num_runs):
            seed = f"groupD_{radius}_{run}"
            config_key = get_config_key(9, True, 3, radius, 100, 2)
            
            # Check if we already have this configuration
            existing_sim = find_matching_simulation(all_results, config_key, 'groupD_')
            if existing_sim:
                print(f"\nReusing existing simulation for Group D - Serving Enqueue Radius: {radius} meters")
                print(f"Configuration: trikes=9, capacity=3, e_radius=100, maxCycles=2")
                # Copy the existing simulation with a new seed
                new_sim = existing_sim.copy()
                new_sim['metadata']['seed'] = seed
                all_results['simulations'].append(new_sim)
                save_progress(all_results, data_dir)
                completed_simulations += 1
                group_d_completed += 1
                update_progress()
            elif config_key not in completed_configs:
                print(f"\nTesting Group D - Serving Enqueue Radius: {radius} meters")
                print(f"Fixed parameters: trikes=9, capacity=3, e_radius=100, maxCycles=2")
                results = run_simulation(
                    9,  # Fixed number of tricycles
                    use_smart_scheduler=True,
                    trike_capacity=3,
                    seed=seed,
                    s_enqueue_radius_meters=radius,
                    enqueue_radius_meters=100,
                    maxCycles=2
                )
                if results:
                    all_results['simulations'].append(results)
                    completed_configs.add(config_key)
                    save_progress(all_results, data_dir)
                    completed_simulations += 1
                    group_d_completed += 1
                    update_progress()

    # Save final results
    final_file = os.path.join(data_dir, f'simulation_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(final_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    # Clean up progress file
    progress_file = os.path.join(data_dir, 'simulation_progress.json')
    if os.path.exists(progress_file):
        os.remove(progress_file)

    print(f"\nFinal Progress Summary:")
    print(f"Group A: {group_a_completed}/{len(tricycle_counts) * num_runs} simulations completed")
    print(f"Group B: {group_b_completed}/{len(tricycle_capacities) * num_runs} simulations completed")
    print(f"Group C: {group_c_completed}/{len(enqueue_radii) * num_runs} simulations completed")
    print(f"Group D: {group_d_completed}/{len(s_enqueue_radii) * num_runs} simulations completed")
    print(f"Total simulations completed: {completed_simulations}/{total_simulations} ({(completed_simulations/total_simulations)*100:.1f}%)")
    print(f"Final results saved to: {final_file}")

if __name__ == '__main__':
    main() 