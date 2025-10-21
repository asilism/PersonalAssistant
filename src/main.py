"""
Main entry point for the Orchestration Service
"""

import asyncio
import sys
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

    # Example requests
    test_requests = [
        "Search the web for recent AI news and summarize the top 3 articles",
        "Read the file README.md and create a summary",
        "Send an email to john@example.com with subject 'Meeting Update' and body 'The meeting is rescheduled to 3 PM'"
    ]

    # Process requests
    for i, request in enumerate(test_requests, 1):
        print(f"\n{'='*80}")
        print(f"Request #{i}: {request}")
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

    print("\n=== All requests processed ===\n")


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
