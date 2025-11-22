#!/usr/bin/env python3
"""
Calculator Agent MCP Server
Provides mathematical calculation tools
"""

import math
from typing import TypedDict
from fastmcp import FastMCP


# Output schema types
class CalculationOutput(TypedDict):
    success: bool
    operation: str
    result: float


# Create FastMCP server
mcp = FastMCP("calculator-agent")


@mcp.tool()
def add(numbers: list[float]) -> CalculationOutput:
    """Add two or more numbers

    Args:
        numbers: Numbers to add

    Returns:
        CalculationOutput: {
            "success": bool,
            "operation": str,
            "result": float
        }

    Example Output:
        {
            "success": true,
            "operation": "addition",
            "result": 150.5
        }

    Key Output Fields:
        - result: The sum of all numbers
        - operation: Type of calculation performed
    """
    if not numbers:
        return {
            "success": False,
            "error": "At least one number required"
        }

    result = sum(numbers)
    return {
        "success": True,
        "operation": "addition",
        "numbers": numbers,
        "result": result
    }


@mcp.tool()
def subtract(numbers: list[float]) -> CalculationOutput:
    """Subtract numbers (first - second - third...)

    Args:
        numbers: Numbers to subtract

    Returns:
        CalculationOutput: {"success": bool, "operation": str, "result": float}

    Example Output:
        {"success": true, "operation": "subtraction", "result": 50.0}

    Key Output Fields:
        - result: The result of subtraction
        - operation: Type of calculation performed
    """
    if not numbers:
        return {
            "success": False,
            "error": "At least one number required"
        }

    result = numbers[0]
    for num in numbers[1:]:
        result -= num

    return {
        "success": True,
        "operation": "subtraction",
        "numbers": numbers,
        "result": result
    }


@mcp.tool()
def multiply(numbers: list[float]) -> CalculationOutput:
    """Multiply two or more numbers

    Args:
        numbers: Numbers to multiply

    Returns:
        CalculationOutput: {"success": bool, "operation": str, "result": float}

    Example Output:
        {"success": true, "operation": "multiplication", "result": 200.0}

    Key Output Fields:
        - result: The product of all numbers
        - operation: Type of calculation performed
    """
    if not numbers:
        return {
            "success": False,
            "error": "At least one number required"
        }

    result = 1
    for num in numbers:
        result *= num

    return {
        "success": True,
        "operation": "multiplication",
        "numbers": numbers,
        "result": result
    }


@mcp.tool()
def divide(numbers: list[float]) -> CalculationOutput:
    """Divide numbers (first / second / third...)

    Args:
        numbers: Numbers to divide

    Returns:
        CalculationOutput: {"success": bool, "operation": str, "result": float}

    Example Output:
        {"success": true, "operation": "division", "result": 2.5}

    Key Output Fields:
        - result: The result of division
        - operation: Type of calculation performed
    """
    if not numbers:
        return {
            "success": False,
            "error": "At least one number required"
        }

    if any(num == 0 for num in numbers[1:]):
        return {
            "success": False,
            "error": "Division by zero"
        }

    result = numbers[0]
    for num in numbers[1:]:
        result /= num

    return {
        "success": True,
        "operation": "division",
        "numbers": numbers,
        "result": result
    }


@mcp.tool()
def power(base: float, exponent: float) -> CalculationOutput:
    """Raise a number to a power

    Args:
        base: Base number
        exponent: Exponent

    Returns:
        CalculationOutput: {"success": bool, "operation": str, "result": float}

    Example Output:
        {"success": true, "operation": "power", "result": 8.0}

    Key Output Fields:
        - result: base^exponent
        - operation: Type of calculation performed
    """
    result = math.pow(base, exponent)
    return {
        "success": True,
        "operation": "power",
        "base": base,
        "exponent": exponent,
        "result": result
    }


if __name__ == "__main__":
    # Run as streamable-HTTP server on port 8003
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8003)
