from typing import Union

def add_numbers(num1: Union[int, float, str], num2: Union[int, float, str]) -> Union[int, float]:
    """Adds two numbers, attempting to convert from string if necessary."""
    try:
        n1 = float(num1)
        n2 = float(num2)
        result = n1 + n2
        # Return int if the result is effectively an integer
        return int(result) if result.is_integer() else result
    except (ValueError, TypeError) as e:
        raise ValueError(f"Could not add inputs '{num1}' and '{num2}'. Ensure they are valid numbers.") from e

# Add more invokable functions here as needed
