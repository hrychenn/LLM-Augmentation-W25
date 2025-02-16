# helpers/hotel_functions.py

import openai
import json

import json
import openai

# Function to parse optional hotel parameters
def parse_hotel_options(adults: int = None, rooms: int = None, price_range: str = None) -> dict:
    """
    Parse optional hotel parameters:
      - adults: Number of adult guests per room (default = 1)
      - rooms: Number of rooms requested (default = 1)
      - price_range: Filter hotel offers by price range (e.g., '200-300' or '-300')
    If not provided, set them to sensible defaults or None.
    """
    return {
        "adults": adults if adults is not None else 1,
        "rooms": rooms if rooms is not None else 1,
        "price_range": price_range  # Can be None if not mentioned
    }

# Hotel options parsing schema for LLM function calling
#Accept price_range, adults, rooms
#Accept adults, travelClass, nonStop, maxPrice
#https://developers.amadeus.com/self-service/category/hotels/api-doc/hotel-search/api-reference
#Reference api doc for appropriate description
parse_hotel_options_schema = {
    "type": "function",  # Required field for OpenAI tools
    "function": {
        "name": "parse_hotel_options",
        "description": "Extract optional hotel parameters: 'adults', 'rooms', and 'price_range'.",
        "parameters": {
        #TODO
            "required": []  # All parameters are optional
        }
    }
}

# Function to call OpenAI API and parse hotel options
def call_parse_hotel_options(user_text: str, model="gpt-4-turbo") -> dict:
    """
    Force the model to produce JSON arguments for parse_hotel_options.
    Returns {adults, rooms, price_range}.
    """
    client = openai.OpenAI()

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful travel assistant. The user may specify optional hotel preferences "
                    "like 'adults', 'rooms', 'price_range'. If not mentioned, set them to null. "
                    "Return only valid JSON arguments for the function call."
                )
            },
            {
                "role": "user",
                "content": user_text
            }
        ],
        tools=[parse_hotel_options_schema],  #
        tool_choice={"type": "function", "function": {"name": "parse_hotel_options"}}, 
        temperature=0
    )

    # Extract function call arguments from the response
    message = completion.choices[0].message
    fn_args = json.loads(message.tool_calls[0].function.arguments) 

    # Call the actual Python function
    result = parse_hotel_options(**fn_args)
    return result