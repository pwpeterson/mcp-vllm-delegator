def reverse_string(s):
    """
    Reverses the input string and returns the reversed string.

    Parameters:
    s (str): The string to be reversed.

    Returns:
    str: The reversed string.

    Example:
    >>> reverse_string("hello")
    'olleh'
    """
    return s[::-1]

# Example usage
if __name__ == "__main__":
    print(reverse_string("hello"))  # Output: 'olleh'
