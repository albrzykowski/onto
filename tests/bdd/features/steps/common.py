"""Shared constants and utilities for BDD steps."""

API_BASE_URL = "http://localhost:8000"


def get_response(context):
    """Get the appropriate response from context attributes."""
    if hasattr(context, "readiness_response"):
        return context.readiness_response
    if hasattr(context, "last_response"):
        return context.last_response
    if hasattr(context, "health_response"):
        return context.health_response
    raise AssertionError("No response available in context")
