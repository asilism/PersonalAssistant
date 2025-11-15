"""
Placeholder Resolver - Resolves placeholders in step inputs using previous step outputs
"""

import ast
import re
from typing import Any, Dict, List, Optional
from .types import Step, StepResult


class PlaceholderResolver:
    """Resolves placeholders like {{step_id}} or {{step_id.field}} in step inputs"""

    # Support {{}} (double braces), ${} (dollar), and {} (single braces) patterns for flexibility
    # Pattern matches: {{...}}, ${...}, or {...}
    PLACEHOLDER_PATTERN = re.compile(r'(\{\{([^}]+)\}\}|\$\{([^}]+)\}|\{([^}]+)\})')

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
        - {{step_id}} or ${step_id} - replaces with entire output
        - {{step_id.field}} or ${step_id.field} - replaces with specific field from output
        - {{step_id.field.nested}} - supports nested field access
        """
        # Find all placeholders in the string
        matches = list(self.PLACEHOLDER_PATTERN.finditer(text))

        if not matches:
            return text

        # If the entire string is a single placeholder, return the value directly
        if len(matches) == 1 and matches[0].group(0) == text:
            # Extract placeholder content (from group 2 for {{}}, group 3 for ${}, or group 4 for {})
            placeholder = matches[0].group(2) or matches[0].group(3) or matches[0].group(4)
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
            # Extract placeholder content (from group 2 for {{}}, group 3 for ${}, or group 4 for {})
            placeholder = match.group(2) or match.group(3) or match.group(4)
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
                        Also supports: "step_1.events[0].id" (Python array indexing)
                        Or expressions: "step_1.attendees + ['new@email.com']"

        Returns:
            The resolved value or None if not found
        """
        # Normalize Python array indexing [N] to dot notation .N
        # Convert: "step_1.events[0].id" -> "step_1.events.0.id"
        normalized_placeholder = self._normalize_array_indexing(placeholder)

        # Check if this is an expression (contains operators or brackets)
        # Note: After normalization, brackets in expressions like [...] will still be present
        if any(op in normalized_placeholder for op in ['+', '-', '*', '/', '[', '(', ',']):
            return self._evaluate_expression(normalized_placeholder)

        parts = normalized_placeholder.split('.')
        step_id = parts[0]

        # Check if step output exists
        if step_id not in self._step_outputs:
            print(f"[PlaceholderResolver] ERROR: Step '{step_id}' not found in registered outputs: {list(self._step_outputs.keys())}")
            return None

        value = self._step_outputs[step_id]
        print(f"[PlaceholderResolver] Resolving '{normalized_placeholder}': Starting with step '{step_id}' = {type(value).__name__}")

        # Navigate through nested fields
        current_path = step_id
        for i, part in enumerate(parts[1:], 1):
            prev_value = value
            if isinstance(value, dict):
                if part in value:
                    value = value[part]
                    current_path += f".{part}"
                    print(f"[PlaceholderResolver]   [{i}/{len(parts)-1}] {current_path} = {type(value).__name__}" +
                          (f" (length {len(value)})" if isinstance(value, (list, dict)) else ""))
                else:
                    available_keys = list(value.keys()) if isinstance(value, dict) else []
                    print(f"[PlaceholderResolver] ERROR: Field '{part}' not found in dict at '{current_path}'. Available keys: {available_keys}")
                    return None
            elif isinstance(value, list):
                # Support array indexing like events.0
                try:
                    index = int(part)
                    if 0 <= index < len(value):
                        value = value[index]
                        current_path += f".{part}"
                        print(f"[PlaceholderResolver]   [{i}/{len(parts)-1}] {current_path} = {type(value).__name__}" +
                              (f" (length {len(value)})" if isinstance(value, (list, dict)) else ""))
                    else:
                        print(f"[PlaceholderResolver] ERROR: Index {index} out of range at '{current_path}'. List has {len(prev_value)} elements (valid indices: 0-{len(prev_value)-1})")
                        return None
                except ValueError:
                    print(f"[PlaceholderResolver] ERROR: Invalid list index '{part}' at '{current_path}'. Expected integer, got '{part}'")
                    return None
            else:
                print(f"[PlaceholderResolver] ERROR: Cannot access field '{part}' on {type(value).__name__} at '{current_path}'. Value is not a dict or list.")
                return None

        print(f"[PlaceholderResolver] ✓ Successfully resolved '{normalized_placeholder}' = {value}")
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

    def _normalize_array_indexing(self, placeholder: str) -> str:
        """
        Normalize Python array indexing to dot notation

        Converts "field[0]" to "field.0", "field[1]" to "field.1", etc.
        Examples:
            "step_1.events[0].id" -> "step_1.events.0.id"
            "step_0.attendees[0]" -> "step_0.attendees.0"

        Args:
            placeholder: The placeholder string with potential array indexing

        Returns:
            Normalized placeholder with dot notation
        """
        # Replace [N] with .N using regex
        # Pattern: [\d+] (bracket with digits inside)
        import re
        normalized = re.sub(r'\[(\d+)\]', r'.\1', placeholder)

        if normalized != placeholder:
            print(f"[PlaceholderResolver] Normalized array indexing: '{placeholder}' -> '{normalized}'")

        return normalized

    def clear(self) -> None:
        """Clear all registered step outputs"""
        self._step_outputs.clear()
        print("[PlaceholderResolver] Cleared all step outputs")
