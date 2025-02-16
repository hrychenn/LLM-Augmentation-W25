import os
import json
import requests

from langchain.chat_models import ChatOpenAI
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.prompts import ChatPromptTemplate

def get_llm(temperature=0.3, model_name="gpt-4"):
    """Returns a ChatOpenAI instance with the specified parameters."""
    openai_api_key = os.getenv("OPENAI_API_KEY")
    return ChatOpenAI(openai_api_key=openai_api_key, temperature=temperature, model_name=model_name)

def parse_location(location_string: str) -> dict:
    """
    Parse a user-supplied location into city, state, country, and clarifications.
    Demonstrates a few-shot approach using a list of dict examples.
    """
    # 1) Define the JSON schema
    schemas = [
        ResponseSchema(name="city", description="City name, or best guess if not explicit"),
        ResponseSchema(name="state", description="State/Province name if applicable, else null or empty"),
        ResponseSchema(name="country", description="Country name or best guess"),
        ResponseSchema(name="clarifications", description="Any extra info or ambiguities")
    ]
    parser = StructuredOutputParser.from_response_schemas(schemas)
    format_instructions = parser.get_format_instructions()

    # 2) Build few-shot examples
    few_shot_examples = [
        {
            "input": "NYC, United States",
            "output": {
                "city": "New York",
                "state": "New York",
                "country": "United States",
                "clarifications": ""
            }
        },
        {
            "input": "Barcelona",
            "output": {
                "city": "Barcelona",
                "state": "",
                "country": "Spain",
                "clarifications": "No state concept in Spain"
            }
        },
        {
            "input": "Tokyo",
            "output": {
                "city": "Tokyo",
                "state": "",
                "country": "Japan",
                "clarifications": "Tokyo is both a city and a prefecture"
            }
        },
        {
            "input": "LA",
            "output": {
                "city": "Los Angeles",
                "state": "California",
                "country": "United States",
                "clarifications": ""
            }
        }
    ]

    # 3) Convert examples to textual format in the prompt
    example_text = "\n".join([
        f"Input: {ex['input']}\nJSON Output: {json.dumps(ex['output'], ensure_ascii=False)}\n"
        for ex in few_shot_examples
    ])

    # 4) Build the final prompt
    prompt = f"""
        You are a helpful travel assistant. You receive a location input and must produce:
        - city
        - state (or empty string if not applicable)
        - country
        - clarifications (if anything is ambiguous or missing)

        Follow these few-shot examples to see how we want the JSON output structured:

        {example_text}

        Now parse this user input:
        "{location_string}"

        Return a JSON object with keys city, state, country, clarifications.

        {format_instructions}
        """

    # 5) Send prompt to the LLM and parse
    llm_response = get_llm().predict(prompt)
    return dict(parser.parse(llm_response))




def process_user_input(user_text: str) -> str:
    """
    Decide which service category the user wants: vacation, flight, hotel, or activities.
    Returns one of these as a JSON snippet: {"service": "<category>"}.
    """
    system_instructions = """
    You are a travel assistant deciding which category fits the user's request.
    The categories: 'vacation', 'flight', 'hotel', 'activities'.
    You MUST return valid JSON in the form: {"service": "<category>"}.
    """

    format_instructions = """
    Return a JSON object in this exact format:
    {
        "service": "<category>"
    }
    Replace <category> with one of: 'vacation', 'flight', 'hotel', 'activities'.
    """

    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template("{system_instructions}"),
        HumanMessagePromptTemplate.from_template(
            "User request: {user_text}\n\n{format_instructions}"
        )
    ]).format_messages(
        system_instructions=system_instructions,
        user_text=user_text,
        format_instructions=format_instructions
    )

    llm_response = get_llm(temperature=0, model_name="gpt-4")(prompt)

    try:
        return json.loads(llm_response.content).get("service", "vacation")
    except json.JSONDecodeError:
        return "vacation"
    except Exception as e:
        print(f"Error processing user input: {e}")
        return "vacation"
