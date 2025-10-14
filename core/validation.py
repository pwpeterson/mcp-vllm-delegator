"""
Validation utilities for LLM responses and code
"""


def validate_llm_code_response(code: str, language: str) -> bool:
    """Enhanced validation for code responses"""
    if not code.strip():
        raise ValueError("LLM returned empty code")

    # Language-specific syntax validation
    if language == "python":
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            raise ValueError(f"Invalid Python syntax: {e}")
    elif language == "javascript":
        # Basic JS validation - check for common syntax errors
        if code.count("{") != code.count("}"):
            raise ValueError("Mismatched braces in JavaScript code")
        if code.count("(") != code.count(")"):
            raise ValueError("Mismatched parentheses in JavaScript code")
    elif language == "typescript":
        # Similar to JavaScript for basic checks
        if code.count("{") != code.count("}"):
            raise ValueError("Mismatched braces in TypeScript code")
        if code.count("(") != code.count(")"):
            raise ValueError("Mismatched parentheses in TypeScript code")
    # Add more languages as needed

    return True


def validate_llm_response(
    content: str, original_content: str = "", language: str | None = None, config=None
) -> bool:
    """Validate LLM response for safety"""
    max_length = (
        config.security.max_response_length if config and config.security else 50000
    )
    if len(content) > max_length:
        raise ValueError("LLM response too large")

    if original_content and len(content) < len(original_content) * 0.3:
        raise ValueError("LLM response suspiciously short")

    # Add code validation for supported languages
    if language:
        validate_llm_code_response(content, language)

    return True
