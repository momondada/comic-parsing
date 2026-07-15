from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

from .. import config

TOKEN_SCOPE = "https://ai.azure.com/.default"

_client = None


def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        if config.AZURE_OPENAI_KEY:
            _client = OpenAI(base_url=config.AZURE_OPENAI_ENDPOINT, api_key=config.AZURE_OPENAI_KEY)
        else:
            token_provider = get_bearer_token_provider(DefaultAzureCredential(), TOKEN_SCOPE)
            _client = OpenAI(base_url=config.AZURE_OPENAI_ENDPOINT, api_key=token_provider)
    return _client
