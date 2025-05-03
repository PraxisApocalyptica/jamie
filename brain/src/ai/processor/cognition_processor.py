import re
import json
import ast

from typing import Dict, List, Any, Callable

from src.ai.capabilities import Cognition 


class CognitionProcessor:

    def parse_function(self, input_string: str) -> Dict[str, Any]:
        """
        Parses a string like 'var = [func1(arg1="val1", arg2=[1, 2]), func2()]'.

        Handles nested structures (lists, dicts) and various Python literals
        (strings, numbers, booleans, None) using `ast.literal_eval`.

        Args:
            input_string: The string to parse.

        Returns:
            A dictionary:
                {'variable_name': str,
                'functions': [{'name': str, 'args': {str: Any}}, ...]}

        Raises:
            ValueError: If the input string format is invalid or parsing fails.
        """
        input_string = input_string.strip()
        # Match variable name and the content within the main brackets
        main_match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\[(.*)\]$', input_string, re.DOTALL)
        if not main_match:
            raise ValueError("Invalid format. Expected 'variable_name = [function_calls]'")

        variable_name = main_match.group(1)
        functions_str = main_match.group(2).strip()
        parsed_functions = []

        if not functions_str: # Handle empty list case
            return {'variable_name': variable_name, 'functions': []}

        # Use a more robust way to split function calls at the top level
        # Find commas that are not inside parentheses, brackets, or braces
        call_start = 0
        balance = {'(': 0, '[': 0, '{': 0}
        in_string = None # Track if inside ' or "

        for i, char in enumerate(functions_str):
            if char in ('"', "'") and (i == 0 or functions_str[i-1] != '\\'): # Handle simple escapes
                if in_string == char:
                    in_string = None
                elif in_string is None:
                    in_string = char
            elif in_string is None:
                if char in balance:
                    balance[char] += 1
                elif char == ')':
                    balance['('] -= 1
                elif char == ']':
                    balance['['] -= 1
                elif char == '}':
                    balance['{'] -= 1

                # Check if we found a top-level comma separating function calls
                if char == ',' and all(v == 0 for v in balance.values()):
                    func_call_str = functions_str[call_start:i].strip()
                    if func_call_str: # Avoid empty strings if there are trailing commas
                        parsed_functions.append(self._parse_single_function_call(func_call_str))
                    call_start = i + 1

        # Add the last function call
        last_func_call_str = functions_str[call_start:].strip()
        if last_func_call_str:
            parsed_functions.append(self._parse_single_function_call(last_func_call_str))

        return {'variable_name': variable_name, 'functions': parsed_functions}

    def _parse_single_function_call(self, func_call_str: str) -> Dict[str, Any]:
        """Helper to parse one 'function_name(arg1=val1, ...)' string."""
        match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*)\)$', func_call_str, re.DOTALL)
        if not match:
            raise ValueError(f"Invalid function call format: '{func_call_str}'")

        function_name = match.group(1)
        args_str = match.group(2).strip()
        args = {}

        if args_str:
            # Parse arguments: find 'key=value' pairs separated by commas at the top level
            arg_start = 0
            balance = {'(': 0, '[': 0, '{': 0}
            in_string = None

            for i, char in enumerate(args_str):
                if char in ('"', "'") and (i == 0 or args_str[i-1] != '\\'):
                    if in_string == char:
                        in_string = None
                    elif in_string is None:
                        in_string = char
                elif in_string is None:
                    if char in balance: balance[char] += 1
                    elif char == ')': balance['('] -= 1
                    elif char == ']': balance['['] -= 1
                    elif char == '}': balance['{'] -= 1

                # Found top-level comma separating arguments or end of string
                if (char == ',' and all(v == 0 for v in balance.values()) and in_string is None) or i == len(args_str) - 1:
                    end_index = i + 1 if i == len(args_str) - 1 else i
                    arg_pair_str = args_str[arg_start:end_index].strip()

                    if arg_pair_str:
                        # Split key=value
                        key_match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=(.*)', arg_pair_str, re.DOTALL)
                        if not key_match:
                            raise ValueError(f"Invalid argument format in '{func_call_str}': '{arg_pair_str}'")

                        key = key_match.group(1).strip()
                        value_str = key_match.group(2).strip()

                        # Safely evaluate the value string
                        try:
                            # Attempt to parse as Python literal (list, dict, str, num, bool, None)
                            value = ast.literal_eval(value_str)
                        except (ValueError, SyntaxError, TypeError):
                            # If literal_eval fails, treat as a simple string
                            # (This handles cases like `context=testing` where `testing` is not quoted)
                            # Remove outer quotes if they exist and weren't handled by literal_eval
                            if (value_str.startswith('"') and value_str.endswith('"')) or \
                                (value_str.startswith("'") and value_str.endswith("'")):
                                value = value_str[1:-1]
                            else:
                                value = value_str

                        args[key] = value
                    arg_start = i + 1 # Move start position past the comma

        return {'name': function_name, 'args': args}


    def create_function_callables(self, parsed_data: Dict[str, Any], cognition_instance: Cognition) -> List[Callable[[], Any]]:
        """
        Creates callable functions from parsed data using a Cognition instance.

        Args:
            parsed_data: The dictionary returned by `parse_function`.
            cognition_instance: An instance implementing the Cognition interface.

        Returns:
            A list of zero-argument callable functions. When called, each executes
            the corresponding method on the cognition_instance with parsed arguments.

        Raises:
            AttributeError: If a function name in parsed_data is not found
                            on the cognition_instance.
        """
        callables = []
        functions_list = parsed_data.get('functions', [])

        for func_info in functions_list:
            func_name = func_info['name']
            args = func_info['args']

            # Find the method on the cognition instance
            try:
                method = getattr(cognition_instance, func_name)
            except AttributeError:
                raise AttributeError(f"Function '{func_name}' not found in {type(cognition_instance).__name__}.")

            # Create a callable closure to capture the method and args correctly
            # Using keyword arguments (**args) is generally best practice here
            def make_callable(m=method, a=args):
                return lambda: m(**a)

            callables.append(make_callable()) # Add the lambda function

        return callables
