"""Shared OpenAI client, model defaults, and helpers — import from here everywhere."""

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from openai import OpenAI

from schema import QueryResponse

load_dotenv()

DEFAULT_CHAT_MODEL = "gpt-4o-mini"

_api_key = os.getenv("OPENAI_API_KEY")

# Native OpenAI SDK (structured outputs, raw completions, etc.)
client = OpenAI(api_key=_api_key)

# LangChain chat model (agents, tools, LCEL)
chat_llm = ChatOpenAI(model=DEFAULT_CHAT_MODEL, api_key=_api_key, temperature=0)


def call_llm(system_prompt: str, user_prompt: str, temperature=0.7):
    response = client.chat.completions.create(
        model=DEFAULT_CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content



