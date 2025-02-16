# helpers/flight_functions.py

import openai
import json


def parse_flight_options(adults: int = None, travelClass: str = None,
                         nonStop: bool = None, maxPrice: int = None) -> dict:
    """
    Accept optional flight parameters. If not mentioned, they come in as None.
    Return final dict with defaults or None as appropriate.
    """
    # If user didn't mention something, keep it None or set a default
    final_adults = adults if adults is not None else 1
    final_class = travelClass  # could be "ECONOMY", "BUSINESS", etc.
    final_non_stop = nonStop if nonStop is not None else False
    final_max_price = maxPrice

    return {
        "adults": final_adults,
        "travelClass": final_class,
        "nonStop": final_non_stop,
        "maxPrice": final_max_price
    }

# Flight options parsing schema for LLM function calling
parse_flight_options_schema = {
    "type": "function",  # Required field for OpenAI tools
    "function": {
        "name": "parse_flight_options",
        "description": (
            "Extract optional flight parameters: 'adults', 'travelClass', 'nonStop', 'maxPrice'. "
            "All are optional. If not mentioned, set them to null or default values."
        ),
        "parameters": {
            "type": "object",  # Function expects a JSON object
            "properties": {
                "adults": {
                    "type": "number",  # Passenger count (default = 1)
                    "description": "Number of adult passengers (default=1 if omitted)."
                },
                "travelClass": {
                    "type": "string",  # Cabin class (ECONOMY, BUSINESS, etc.)
                    "description": "Cabin type (e.g., 'ECONOMY' or 'BUSINESS')."
                },
                "nonStop": {
                    "type": "boolean",  # True => direct flights only
                    "description": "True for non-stop flights only, False otherwise."
                },
                "maxPrice": {
                    "type": "number",  # Max price in USD
                    "description": "Maximum price in USD (null if unspecified)."
                }
            },
            "required": []  # No required fields, all are optional
        }
    }
}

# Function to call OpenAI API and parse flight options
def call_parse_flight_options(user_text: str, model="gpt-4-turbo") -> dict:
    """
    Forces the LLM to return structured arguments for 'parse_flight_options'.
    Extracts optional flight parameters and returns them in a dictionary.
    """
    client = openai.OpenAI()  # Ensure we use the correct API client

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful travel assistant. The user may specify optional flight preferences.\n"
                    "Possible fields: 'adults', 'travelClass', 'nonStop', 'maxPrice'.\n"
                    "If not mentioned, set them to null.\n"
                    "Return JSON arguments only, without extra text."
                )
            },
            {
                "role": "user",
                "content": user_text
            }
        ],
        tools=[parse_flight_options_schema], 
        tool_choice={"type": "function", "function": {"name": "parse_flight_options"}},  # Enforce function call
    )

    # Extract function call arguments from the response
    message = completion.choices[0].message
    fn_args = json.loads(message.tool_calls[0].function.arguments)  

    # Call the actual function with extracted arguments
    result = parse_flight_options(**fn_args)
    print(result)
    return result
