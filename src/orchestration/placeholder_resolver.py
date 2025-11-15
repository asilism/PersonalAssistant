"""
Placeholder Resolver - Resolves placeholders in step inputs using previous step outputs
"""

import ast
import re
from typing import Any, Dict, List, Optional
from .types import Step, StepResult


class PlaceholderResolver:
    """Resolves placeholders like {{step_id}} or {{step_id.field}} in step inputs"""

    PLACEHOLDER_PATTERN = re.compile(r'\{\{([^}]+)\}\}')

    def __init__(self):
        self._step_outputs: Dict[str, Any] = {}

    def register_step_result(self, step_id: str, output: Any) -> None:
        """
        Register a step's output for later placeholder resolution

        Args:
            step_id: The step ID
            output: The step's output (can be dict, list, or primitive)
        """
        self._step_outputs[step_id] = output
        print(f"[PlaceholderResolver] Registered output for step '{step_id}': {output}")

    def resolve_step_input(self, step: Step) -> Step:
        """
        Resolve all placeholders in a step's input

        Args:
            step: The step to resolve placeholders for

        Returns:
            A new Step with placeholders resolved
        """
        resolved_input = self._resolve_dict(step.input)

        # Create a new step with resolved input
        return Step(
            step_id=step.step_id,
            tool_name=step.tool_name,
            input=resolved_input,
            description=step.description,
            dependencies=step.dependencies
        )

    def _resolve_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively resolve placeholders in a dictionary"""
        resolved = {}
        for key, value in data.items():
            resolved[key] = self._resolve_value(value)
        return resolved

    def _resolve_value(self, value: Any) -> Any:
        """Resolve placeholders in a single value"""
        if isinstance(value, str):
            return self._resolve_string(value)
        elif isinstance(value, dict):
            return self._resolve_dict(value)
        elif isinstance(value, list):
            return [self._resolve_value(item) for item in value]
        else:
            return value

    def _resolve_string(self, text: str) -> Any:
        """
        Resolve placeholders in a string

        Supports:
        - {{step_id}} - replaces with entire output
        - {{step_id.field}} - replaces with specific field from output
        - {{step_id.field.nested}} - supports nested field access
        """
        # Find all placeholders in the string
        matches = list(self.PLACEHOLDER_PATTERN.finditer(text))

        if not matches:
            return text

        # If the entire string is a single placeholder, return the value directly
        if len(matches) == 1 and matches[0].group(0) == text:
            placeholder = matches[0].group(1)
            value = self._get_placeholder_value(placeholder)
            if value is not None:
                print(f"[PlaceholderResolver] Resolved '{text}' -> {value}")
                return value
            else:
                print(f"[PlaceholderResolver] WARNING: Could not resolve placeholder '{text}'")
                return text

        # If there are multiple placeholders or mixed text, do string replacement
        resolved_text = text
        for match in reversed(matches):  # Process in reverse to maintain positions
            placeholder = match.group(1)
            value = self._get_placeholder_value(placeholder)
            if value is not None:
                # Convert value to string for insertion
                str_value = str(value) if not isinstance(value, str) else value
                resolved_text = resolved_text[:match.start()] + str_value + resolved_text[match.end():]
                print(f"[PlaceholderResolver] Replaced '{match.group(0)}' with '{str_value}'")
            else:
                print(f"[PlaceholderResolver] WARNING: Could not resolve placeholder '{match.group(0)}'")

        return resolved_text

    def _get_placeholder_value(self, placeholder: str) -> Optional[Any]:
        """
        Get the value for a placeholder

        Args:
            placeholder: The placeholder content (without {{ }})
                        Examples: "step_1", "step_1.id", "step_1.events.0.id"
                        Or expressions: "step_1.attendees + ['new@email.com']"

        Returns:
            The resolved value or None if not found
        """
        # Check if this is an expression (contains operators or brackets)
        if any(op in placeholder for op in ['+', '-', '*', '/', '[', '(', ',']):
            return self._evaluate_expression(placeholder)

        parts = placeholder.split('.')
        step_id = parts[0]

        # Check if step output exists
        if step_id not in self._step_outputs:
            print(f"[PlaceholderResolver] Step '{step_id}' not found in outputs")
            return None

        value = self._step_outputs[step_id]

        # Navigate through nested fields
        for part in parts[1:]:
            if isinstance(value, dict):
                if part in value:
                    value = value[part]
                else:
                    print(f"[PlaceholderResolver] Field '{part}' not found in {value}")
                    return None
            elif isinstance(value, list):
                # Support array indexing like events.0
                try:
                    index = int(part)
                    if 0 <= index < len(value):
                        value = value[index]
                    else:
                        print(f"[PlaceholderResolver] Index {index} out of range for list of length {len(value)}")
                        return None
                except ValueError:
                    print(f"[PlaceholderResolver] Invalid list index: '{part}'")
                    return None
            else:
                print(f"[PlaceholderResolver] Cannot access field '{part}' on {type(value)}")
                return None

        return value

    def _evaluate_expression(self, expression: str) -> Optional[Any]:
        """
        Safely evaluate a Python expression with access to step outputs

        Args:
            expression: A Python expression like "step_1.attendees + ['new@email.com']"

        Returns:
            The evaluated result or None if evaluation fails
        """
        try:
            # Create a namespace with step outputs for evaluation
            namespace = {}

            # Add step outputs to namespace
            # For each step, add it directly and also extract nested fields
            for step_id, output in self._step_outputs.items():
                namespace[step_id] = output
                # If output is a dict with common wrapper keys like 'event', 'data', etc.
                # create a flattened version for easier access
                if isinstance(output, dict):
                    # Check for common data wrapper patterns
                    for wrapper_key in ['event', 'data', 'result', 'value']:
                        if wrapper_key in output and isinstance(output[wrapper_key], dict):
                            # Create a merged namespace that includes both wrapped and unwrapped data
                            # This allows step_1.field to work even if the actual structure is step_1.event.field
                            wrapped_data = output[wrapper_key]
                            # Create a custom dict that tries both direct and wrapped access
                            namespace[step_id] = self._create_smart_dict(output, wrapped_data)
                            break
                    else:
                        namespace[step_id] = output

            # Build a context that supports field access
            # Replace step_id.field with step_id['field'] for dict access
            eval_expr = self._transform_expression(expression)

            print(f"[PlaceholderResolver] Evaluating expression: {eval_expr}")

            # Evaluate with restricted built-ins for safety
            result = eval(eval_expr, {"__builtins__": {}}, namespace)

            print(f"[PlaceholderResolver] Expression '{expression}' evaluated to: {result}")
            return result

        except Exception as e:
            print(f"[PlaceholderResolver] Error evaluating expression '{expression}': {e}")
            return None

    def _create_smart_dict(self, original: dict, wrapped_data: dict) -> dict:
        """
        Create a dictionary that tries wrapped data first, then falls back to original

        Args:
            original: The original dict (e.g., {'success': True, 'event': {...}})
            wrapped_data: The wrapped data dict (e.g., the 'event' dict)

        Returns:
            A merged dict with smart lookup
        """
        class SmartDict(dict):
            def __init__(self, orig, wrapped):
                super().__init__(orig)
                self._original = orig
                self._wrapped = wrapped

            def __getitem__(self, key):
                # Try wrapped data first (for convenient access)
                if key in self._wrapped:
                    return self._wrapped[key]
                # Fall back to original
                return self._original[key]

        return SmartDict(original, wrapped_data)

    def _transform_expression(self, expression: str) -> str:
        """
        Transform step_id.field syntax to step_id['field'] for dict access

        Args:
            expression: Original expression like "step_1.attendees + ['new@email.com']"

        Returns:
            Transformed expression like "step_1['attendees'] + ['new@email.com']"
        """
        # We need to be careful not to transform dots inside strings
        # Strategy: Replace dots only outside of quoted strings

        result = []
        i = 0
        in_string = False
        string_char = None

        while i < len(expression):
            char = expression[i]

            # Track if we're inside a string
            if char in ('"', "'"):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None
                result.append(char)
                i += 1
            elif not in_string and (char.isalpha() or char.isdigit() or char == '_'):
                # Start of an identifier
                identifier_start = i
                while i < len(expression) and (expression[i].isalnum() or expression[i] == '_'):
                    i += 1

                identifier = expression[identifier_start:i]

                # Check for chained field access (e.g., step_1.event.attendees)
                fields = [identifier]
                while i < len(expression) and expression[i] == '.':
                    # Look ahead to see if this is field access (word.word pattern)
                    j = i + 1
                    if j < len(expression) and (expression[j].isalpha() or expression[j] == '_'):
                        # This is field access
                        field_start = j
                        while j < len(expression) and (expression[j].isalnum() or expression[j] == '_'):
                            j += 1
                        field = expression[field_start:j]
                        fields.append(field)
                        i = j
                    else:
                        # Not field access, break the chain
                        break

                # Build the bracket notation
                if len(fields) > 1:
                    # Multiple fields, use bracket notation for all but the first
                    result.append(fields[0])
                    for field in fields[1:]:
                        result.append(f"['{field}']")
                else:
                    # Single identifier, no transformation needed
                    result.append(identifier)
            else:
                result.append(char)
                i += 1

        return ''.join(result)

    def clear(self) -> None:
        """Clear all registered step outputs"""
        self._step_outputs.clear()
        print("[PlaceholderResolver] Cleared all step outputs")
