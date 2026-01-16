"""
Test script for Manus-style multi-agent system
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from manus.coordinator import ManusCoordinator


async def test_simple_request():
    """Test a simple request using Manus system"""
    print("=" * 80)
    print("Testing Manus Multi-Agent System")
    print("=" * 80)

    # Create coordinator
    coordinator = ManusCoordinator(
        user_id="test_user",
        tenant="test_tenant"
    )

    # Simple test request
    request = "What's the weather like today?"

    print(f"\nRequest: {request}")
    print("-" * 80)

    try:
        # Run the request
        result = await coordinator.run(
            request=request,
            max_wait_time=30  # 30 seconds timeout
        )

        print("\n" + "=" * 80)
        print("RESULT")
        print("=" * 80)

        print(f"\nSuccess: {result.get('success')}")
        print(f"Message: {result.get('message')}")
        print(f"Session ID: {result.get('session_id')}")
        print(f"Workspace: {result.get('workspace_path')}")

        if result.get('final_response'):
            print(f"\nFinal Response:\n{result.get('final_response')}")

        if result.get('results'):
            print(f"\nAgent Results:")
            for agent_name, agent_result in result['results'].items():
                print(f"\n  {agent_name}:")
                print(f"    Status: {agent_result.get('status')}")
                print(f"    Summary: {agent_result.get('summary', '')[:200]}")

        # Cleanup
        await coordinator.cleanup()

        return result

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

        # Cleanup on error
        await coordinator.cleanup()

        return None


async def test_workspace_structure():
    """Test that workspace structure is created correctly"""
    print("\n" + "=" * 80)
    print("Testing Workspace Structure")
    print("=" * 80)

    coordinator = ManusCoordinator(
        user_id="test_user",
        tenant="test_tenant"
    )

    request = "List files in the current directory"

    try:
        result = await coordinator.run(
            request=request,
            max_wait_time=30
        )

        # Check workspace structure
        workspace_path = Path(result.get('workspace_path'))

        print(f"\nWorkspace path: {workspace_path}")
        print("\nWorkspace structure:")

        if workspace_path.exists():
            for item in workspace_path.rglob("*"):
                if item.is_file():
                    rel_path = item.relative_to(workspace_path)
                    print(f"  {rel_path}")

            # Read plan.md if exists
            plan_file = workspace_path / "plan.md"
            if plan_file.exists():
                print("\n" + "-" * 80)
                print("plan.md content:")
                print("-" * 80)
                print(plan_file.read_text())

        await coordinator.cleanup()

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        await coordinator.cleanup()


async def main():
    """Run all tests"""
    print("Starting Manus System Tests\n")

    # Test 1: Simple request
    await test_simple_request()

    # Test 2: Workspace structure
    await test_workspace_structure()

    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
