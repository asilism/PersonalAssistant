#!/usr/bin/env python3
"""
Test runner for PersonalAssistant
Runs all test questions and generates a scorecard
"""

import asyncio
import json
import csv
import sys
import os
from datetime import datetime
from typing import Dict, List, Any
import time

# Set dummy API key for testing if not already set
# NOTE: A valid API key is required for tests to actually execute.
# Set ANTHROPIC_API_KEY environment variable with a valid key before running tests.
if not os.getenv("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = "test-api-key-for-unit-tests"
    print("⚠️  Warning: No ANTHROPIC_API_KEY set. Using dummy key - tests will fail at execution.")
    print("   Set a valid API key: export ANTHROPIC_API_KEY=your-key-here\n")

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from orchestration.orchestrator import Orchestrator


class TestRunner:
    """Runner for executing test questions and generating scorecards"""

    def __init__(self, user_id: str = "test_user", tenant: str = "test_tenant"):
        self.user_id = user_id
        self.tenant = tenant
        self.results = []
        self.orchestrator = None  # Will be initialized once before running tests

    async def run_single_question(self, question_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single test question"""
        question_id = question_data.get("id")
        category = question_data.get("category")
        question = question_data.get("question")
        expected_tools = question_data.get("expected_tools", [])

        print(f"\n{'='*80}")
        print(f"Running Question {question_id}: {category}")
        print(f"Question: {question}")
        print(f"Expected tools: {expected_tools}")
        print(f"{'='*80}")

        # Initialize result
        result = {
            "question_id": question_id,
            "category": category,
            "question": question,
            "expected_tools": expected_tools,
            "actual_tools_used": [],
            "output": "",
            "status": "unknown",
            "error_message": "",
            "execution_time_seconds": 0,
            "timestamp": datetime.now().isoformat()
        }

        start_time = time.time()

        try:
            # Generate a unique session ID for this test
            session_id = f"test_{question_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Run the orchestration using the shared orchestrator instance
            response = await self.orchestrator.run(
                session_id=session_id,
                request_text=question
            )

            # Extract results
            if response:
                # Map orchestrator response to test result format
                result["output"] = str(response.get("message", ""))
                if response.get("success"):
                    result["status"] = "completed"
                else:
                    result["status"] = "failed"

                # Extract tools used from the plan
                if "plan" in response and response["plan"]:
                    plan = response["plan"]
                    if isinstance(plan, dict) and "task_groups" in plan:
                        tools_used = []
                        for task_group in plan["task_groups"]:
                            if "tasks" in task_group:
                                for task in task_group["tasks"]:
                                    if "tool" in task:
                                        tools_used.append(task["tool"])
                        result["actual_tools_used"] = tools_used

                # Determine success based on status and expected tools
                if result["status"] == "completed":
                    # Check if all expected tools were used
                    tools_match = all(tool in result["actual_tools_used"] for tool in expected_tools)
                    result["status"] = "success" if tools_match else "partial_success"
                    if not tools_match:
                        result["error_message"] = f"Tool mismatch. Expected: {expected_tools}, Got: {result['actual_tools_used']}"
                else:
                    result["status"] = "failure"

            else:
                result["status"] = "failure"
                result["error_message"] = "No response from orchestrator"

        except Exception as e:
            result["status"] = "error"
            result["error_message"] = str(e)
            print(f"❌ Error: {str(e)}")

        finally:
            end_time = time.time()
            result["execution_time_seconds"] = round(end_time - start_time, 2)

        # Print result
        status_icon = "✓" if result["status"] == "success" else "⚠" if result["status"] == "partial_success" else "✗"
        print(f"\n{status_icon} Status: {result['status']}")
        print(f"Tools used: {result['actual_tools_used']}")
        print(f"Execution time: {result['execution_time_seconds']}s")

        return result

    async def run_all_questions(self, questions_file: str = "test_questions.json"):
        """Run all test questions from the JSON file"""
        print(f"\n{'='*80}")
        print("PersonalAssistant Test Runner")
        print(f"{'='*80}\n")

        # Initialize orchestrator once for all tests
        print("Initializing orchestrator and loading MCP servers...")
        self.orchestrator = Orchestrator(self.user_id, self.tenant)
        # Trigger initialization by calling _initialize directly
        await self.orchestrator._initialize()
        print(f"✓ Orchestrator initialized\n")

        # Load questions
        with open(questions_file, 'r') as f:
            questions_data = json.load(f)

        # Collect all questions
        all_questions = []
        all_questions.extend(questions_data.get("single_agent_questions", []))
        all_questions.extend(questions_data.get("multi_agent_questions", []))
        all_questions.extend(questions_data.get("rpa_included_questions", []))

        print(f"Loaded {len(all_questions)} test questions")
        print(f"  - Single agent: {len(questions_data.get('single_agent_questions', []))}")
        print(f"  - Multi agent: {len(questions_data.get('multi_agent_questions', []))}")
        print(f"  - RPA included: {len(questions_data.get('rpa_included_questions', []))}")

        # Run each question
        for question_data in all_questions:
            result = await self.run_single_question(question_data)
            self.results.append(result)

            # Small delay between questions
            await asyncio.sleep(0.5)

        return self.results

    def generate_csv_report(self, output_file: str = "test_results.csv"):
        """Generate CSV scorecard"""
        print(f"\n{'='*80}")
        print(f"Generating CSV report: {output_file}")
        print(f"{'='*80}")

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                "question_id",
                "category",
                "question",
                "expected_tools",
                "actual_tools_used",
                "status",
                "output",
                "error_message",
                "execution_time_seconds",
                "timestamp"
            ]

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in self.results:
                # Convert lists to strings for CSV
                csv_result = result.copy()
                csv_result["expected_tools"] = ", ".join(result["expected_tools"])
                csv_result["actual_tools_used"] = ", ".join(result["actual_tools_used"])
                writer.writerow(csv_result)

        print(f"✓ CSV report saved to {output_file}")

    def generate_json_report(self, output_file: str = "test_results.json"):
        """Generate JSON scorecard"""
        print(f"\n{'='*80}")
        print(f"Generating JSON report: {output_file}")
        print(f"{'='*80}")

        # Add summary statistics
        total = len(self.results)
        success = sum(1 for r in self.results if r["status"] == "success")
        partial = sum(1 for r in self.results if r["status"] == "partial_success")
        failure = sum(1 for r in self.results if r["status"] == "failure")
        error = sum(1 for r in self.results if r["status"] == "error")

        report = {
            "summary": {
                "total_questions": total,
                "success": success,
                "partial_success": partial,
                "failure": failure,
                "error": error,
                "success_rate": round(success / total * 100, 2) if total > 0 else 0,
                "generated_at": datetime.now().isoformat()
            },
            "results": self.results
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"✓ JSON report saved to {output_file}")
        print(f"\nSummary Statistics:")
        print(f"  Total: {total}")
        print(f"  Success: {success} ({round(success / total * 100, 1)}%)")
        print(f"  Partial Success: {partial} ({round(partial / total * 100, 1)}%)")
        print(f"  Failure: {failure} ({round(failure / total * 100, 1)}%)")
        print(f"  Error: {error} ({round(error / total * 100, 1)}%)")

    def print_summary(self):
        """Print summary to console"""
        print(f"\n{'='*80}")
        print("Test Execution Complete")
        print(f"{'='*80}\n")

        # Category breakdown
        categories = {}
        for result in self.results:
            cat = result["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "success": 0, "partial": 0, "failure": 0, "error": 0}

            categories[cat]["total"] += 1
            if result["status"] == "success":
                categories[cat]["success"] += 1
            elif result["status"] == "partial_success":
                categories[cat]["partial"] += 1
            elif result["status"] == "failure":
                categories[cat]["failure"] += 1
            else:
                categories[cat]["error"] += 1

        print("Results by Category:")
        print(f"{'Category':<30} {'Total':<8} {'Success':<10} {'Partial':<10} {'Failure':<10} {'Error':<8}")
        print("-" * 80)

        for cat, stats in sorted(categories.items()):
            print(f"{cat:<30} {stats['total']:<8} {stats['success']:<10} {stats['partial']:<10} {stats['failure']:<10} {stats['error']:<8}")


async def main():
    """Main entry point"""
    runner = TestRunner()

    try:
        # Run all questions
        await runner.run_all_questions()

        # Generate reports
        runner.generate_csv_report("test_results.csv")
        runner.generate_json_report("test_results.json")

        # Print summary
        runner.print_summary()

        print(f"\n{'='*80}")
        print("Reports generated:")
        print("  - test_results.csv (CSV format)")
        print("  - test_results.json (JSON format with summary)")
        print(f"{'='*80}\n")

    except KeyboardInterrupt:
        print("\n\nTest execution interrupted by user")
        if runner.results:
            print("Generating partial reports...")
            runner.generate_csv_report("test_results_partial.csv")
            runner.generate_json_report("test_results_partial.json")
            runner.print_summary()
    except Exception as e:
        print(f"\n\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
