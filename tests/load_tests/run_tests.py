#!/usr/bin/env python3
"""
Load Test Runner Script
"""
import os
import sys
import json
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

from config import (
    SCENARIOS,
    ENVIRONMENT,
    RUN_SETTINGS,
    DB_TEST_DATA,
    TEST_USERS,
    TEST_APPS
)
from test_data import TestDataManager

def setup_test_environment(env="development"):
    """Set up the test environment with required data"""
    print(f"Setting up test environment: {env}")
    
    # Set environment variables
    os.environ["LOAD_TEST_ENV"] = env
    os.environ["LOAD_TEST_HOST"] = ENVIRONMENT[env]["host"]
    
    if RUN_SETTINGS["generate_test_data"]:
        print("Generating test data...")
        data_manager = TestDataManager(ENVIRONMENT[env]["host"])
        if not data_manager.setup_test_data(TEST_USERS, TEST_APPS):
            print("Error: Failed to set up test data")
            sys.exit(1)
        return data_manager
    return None

def run_load_test(scenario="light_load"):
    """Run the load test with specified scenario"""
    if scenario not in SCENARIOS:
        print(f"Error: Invalid scenario '{scenario}'")
        sys.exit(1)
        
    scenario_config = SCENARIOS[scenario]
    
    # Create results directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path(f"results/{timestamp}_{scenario}")
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # Get the directory of the current script
    current_dir = Path(__file__).parent
    
    # Build locust command with correct path to locustfile.py
    cmd = [
        "locust",
        "-f", str(current_dir / "locustfile.py"),
        "--headless",
        "--users", str(scenario_config["users"]),
        "--spawn-rate", str(scenario_config["spawn_rate"]),
        "--run-time", scenario_config["run_time"],
        "--html", str(results_dir / "report.html"),
        "--csv", str(results_dir / "stats"),
        "--host", os.environ["LOAD_TEST_HOST"]
    ]
    
    print(f"Running load test with scenario: {scenario}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Load test completed. Results saved in: {results_dir}")
    except subprocess.CalledProcessError as e:
        print(f"Error running load test: {e}")
        sys.exit(1)

def cleanup_test_environment(data_manager=None):
    """Clean up test data and environment"""
    if RUN_SETTINGS["cleanup_after"] and data_manager:
        print("Cleaning up test environment...")
        if not data_manager.cleanup_test_data():
            print("Warning: Failed to clean up some test data")

def main():
    parser = argparse.ArgumentParser(description="Run load tests for Crowdfund AI Platform")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="light_load",
        help="Load test scenario to run"
    )
    parser.add_argument(
        "--env",
        choices=list(ENVIRONMENT.keys()),
        default="development",
        help="Environment to run tests against"
    )
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Skip test environment setup"
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Skip test environment cleanup"
    )
    
    args = parser.parse_args()
    data_manager = None
    
    try:
        if not args.skip_setup:
            data_manager = setup_test_environment(args.env)
            
        run_load_test(args.scenario)
        
        if not args.skip_cleanup:
            cleanup_test_environment(data_manager)
            
    except KeyboardInterrupt:
        print("\nLoad test interrupted by user")
        cleanup_test_environment(data_manager)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        cleanup_test_environment(data_manager)
        sys.exit(1)

if __name__ == "__main__":
    main() 