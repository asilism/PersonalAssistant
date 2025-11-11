"""
Main entry point for the Orchestration Service
"""

import asyncio
import sys
import json
import os
from orchestration.orchestrator import Orchestrator


async def main():
    """Main function"""

    # Example usage
    print("=== Personal Assistant Orchestration Service ===\n")

    # Initialize orchestrator
    user_id = "test_user"
    tenant = "test_tenant"
    session_id = "session_001"

    orchestrator = Orchestrator(user_id=user_id, tenant=tenant)

    # Load test requests from file
    test_requests_file = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "test_requests.json"
    )

    try:
        with open(test_requests_file, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        print(f"Loaded {len(test_data)} test cases from {test_requests_file}\n")
    except FileNotFoundError:
        print(f"Error: Test requests file not found at {test_requests_file}")
        print("Please create the test_requests.json file in the project root.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in test requests file: {e}")
        sys.exit(1)

    # Process requests
    for test_case in test_data:
        test_id = test_case.get('id', 'N/A')
        description = test_case.get('description', 'No description')
        request = test_case.get('request', '')

        print(f"\n{'='*80}")
        print(f"Test Case #{test_id}: {description}")
        print(f"Request: {request}")
        print(f"{'='*80}\n")

        try:
            result = await orchestrator.run(
                session_id=session_id,
                request_text=request
            )

            print(f"\n{'='*80}")
            print(f"Result:")
            print(f"  Success: {result['success']}")
            print(f"  Message: {result['message']}")
            if result.get('results'):
                print(f"  Results: {result['results']}")
            print(f"  Execution Time: {result['execution_time']:.2f}s")
            if result.get('plan_id'):
                print(f"  Plan ID: {result['plan_id']}")
            print(f"{'='*80}\n")

        except Exception as e:
            print(f"\nError processing request: {e}\n")
            import traceback
            traceback.print_exc()

    print("\n=== All test cases processed ===\n")


if __name__ == "__main__":
    # Check for ANTHROPIC_API_KEY
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable is not set")
        print("Please set it before running:")
        print("  export ANTHROPIC_API_KEY=your_api_key")
        sys.exit(1)

    # Run main
    asyncio.run(main())
