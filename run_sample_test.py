#!/usr/bin/env python3
"""
Sample test runner for PersonalAssistant
Runs a small subset of test questions for quick validation
"""

import asyncio
import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from run_tests import TestRunner


async def main():
    """Run a sample of test questions"""
    print(f"\n{'='*80}")
    print("PersonalAssistant Sample Test Runner")
    print("Running first 5 questions from each category")
    print(f"{'='*80}\n")

    runner = TestRunner()

    # Load questions
    with open("test_questions.json", 'r') as f:
        questions_data = json.load(f)

    # Get sample questions (first 5 from each category)
    sample_questions = []
    sample_questions.extend(questions_data.get("single_agent_questions", [])[:5])
    sample_questions.extend(questions_data.get("multi_agent_questions", [])[:5])
    sample_questions.extend(questions_data.get("rpa_included_questions", [])[:5])

    print(f"Running {len(sample_questions)} sample questions...\n")

    # Run each question
    for question_data in sample_questions:
        result = await runner.run_single_question(question_data)
        runner.results.append(result)
        await asyncio.sleep(0.5)

    # Generate reports
    runner.generate_csv_report("test_results_sample.csv")
    runner.generate_json_report("test_results_sample.json")
    runner.print_summary()

    print(f"\n{'='*80}")
    print("Sample test reports generated:")
    print("  - test_results_sample.csv")
    print("  - test_results_sample.json")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(main())
