"""Your agent's tools live here.

A tool is a plain function with type hints + a docstring, wrapped with @tool. The
docstring is what the LLM reads to decide when to call it, so make it clear.
"""

from roscoe.tools import tool


@tool
def get_weather(city: str) -> dict:
    """Get the current weather for a city. Use when the user asks about weather."""
    # Replace this stub with a real API call.
    fake = {"london": "15C rainy", "delhi": "38C sunny", "tokyo": "22C clear"}
    return {"city": city, "weather": fake.get(city.lower(), "unknown")}


# Add more @tool functions and include them in the list below.
TOOLS = [get_weather]
