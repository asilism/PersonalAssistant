# Testing Guide

This guide explains how to run the test suite for the PersonalAssistant project.

## Test Structure

The test suite contains **100 test questions** organized into three categories:

1. **Single Agent Questions (25)** - Questions that use only one tool/agent
   - Mail agent: 6 questions
   - Calendar agent: 6 questions
   - Jira agent: 6 questions
   - Calculator agent: 7 questions

2. **Multi-Agent Questions (25)** - Questions that use multiple tools (max 3) without RPA
   - Mail + Calendar
   - Jira + Mail
   - Calendar + Jira
   - Calculator + other agents
   - Various 3-agent combinations

3. **RPA Included Questions (50)** - Questions that include the RPA agent
   - RPA alone
   - RPA + Mail
   - RPA + Calendar
   - RPA + Jira
   - RPA + Calculator
   - Complex multi-agent scenarios with RPA

## Test Files

- `test_questions.json` - Contains all 100 test questions
- `run_tests.py` - Full test runner that executes all 100 questions
- `run_sample_test.py` - Sample test runner that executes first 5 from each category (15 total)

## Running Tests

### Full Test Suite (100 questions)

```bash
python run_tests.py
```

This will:
- Execute all 100 test questions sequentially
- Generate detailed results for each question
- Create two output files:
  - `test_results.csv` - CSV format for spreadsheet analysis
  - `test_results.json` - JSON format with summary statistics

**Note:** Running all 100 questions may take significant time.

### Sample Test (15 questions)

For quick validation, run the sample test:

```bash
python run_sample_test.py
```

This will:
- Execute first 5 questions from each category (15 total)
- Generate sample output files:
  - `test_results_sample.csv`
  - `test_results_sample.json`

## Output Format

### CSV Report

The CSV file contains the following columns:

| Column | Description |
|--------|-------------|
| question_id | Unique question identifier (1-100) |
| category | Question category (e.g., "Mail - Single", "Multi-Agent", "RPA Included") |
| question | The actual question text |
| expected_tools | Tools that should be used (comma-separated) |
| actual_tools_used | Tools that were actually used (comma-separated) |
| status | success / partial_success / failure / error |
| output | Summary output from the orchestrator |
| error_message | Error details if status is not success |
| execution_time_seconds | Time taken to execute the question |
| timestamp | ISO format timestamp of execution |

### JSON Report

The JSON file contains:

```json
{
  "summary": {
    "total_questions": 100,
    "success": 85,
    "partial_success": 10,
    "failure": 3,
    "error": 2,
    "success_rate": 85.0,
    "generated_at": "2025-11-11T15:30:00.123456"
  },
  "results": [
    {
      "question_id": 1,
      "category": "Mail - Single",
      "question": "Send an email to john@example.com...",
      "expected_tools": ["send_email"],
      "actual_tools_used": ["send_email"],
      "status": "success",
      "output": "Email sent successfully",
      "error_message": "",
      "execution_time_seconds": 2.34,
      "timestamp": "2025-11-11T15:30:00.123456"
    },
    ...
  ]
}
```

## Status Codes

- **success** - Question executed successfully and all expected tools were used
- **partial_success** - Question executed but tool usage didn't match expectations
- **failure** - Question execution failed but didn't throw an error
- **error** - An exception occurred during execution

## Analyzing Results

### Using CSV

Open `test_results.csv` in Excel, Google Sheets, or any spreadsheet software to:
- Sort by status to see failures first
- Filter by category to analyze specific agent types
- Calculate success rates per category
- Identify patterns in failures

### Using JSON

The JSON format is useful for:
- Programmatic analysis
- Importing into data analysis tools
- Quick summary statistics viewing
- Integration with CI/CD pipelines

## Adding New Test Questions

To add new test questions:

1. Open `test_questions.json`
2. Add your question to the appropriate array:
   - `single_agent_questions` - For single-tool questions
   - `multi_agent_questions` - For multi-tool questions (no RPA)
   - `rpa_included_questions` - For questions involving RPA

3. Follow this format:

```json
{
  "id": 101,
  "category": "Your Category",
  "agent": "agent_name",
  "agents": ["agent1", "agent2"],
  "question": "Your question text here",
  "expected_tools": ["tool1", "tool2"]
}
```

## Continuous Integration

You can integrate the test runner into your CI/CD pipeline:

```bash
# Run tests and capture exit code
python run_tests.py
EXIT_CODE=$?

# Check for failures
if [ $EXIT_CODE -ne 0 ]; then
  echo "Tests failed!"
  exit 1
fi
```

## Troubleshooting

### Tests are slow
- Use `run_sample_test.py` for quick validation
- Consider running tests in parallel (future enhancement)

### All tests failing
- Check that all MCP servers are running
- Verify `.env` file is configured correctly
- Ensure all dependencies are installed

### Tool mismatch errors
- Review the orchestrator's planning logic
- Check if tool names have changed
- Verify MCP server implementations

## Future Enhancements

Planned improvements:
- [ ] Parallel test execution
- [ ] HTML report generation
- [ ] Test filtering by category
- [ ] Performance benchmarking
- [ ] Regression testing
- [ ] Integration with pytest
