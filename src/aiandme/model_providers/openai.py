from os import getenv
from openai import OpenAI

#
# Handle communications with LLM
#
ALLOWED_MAX_OUT_TOKENS = 4096  # max allowed tokens
DEFAULT_MAX_OUT_TOKENS = 512  # max numbers of tokens each LLM ping can deliver
MAX_RETRY_COUNTER = 5  # how many times to retry an API call before returning error
LLM_PING_TIMEOUT = 30  # llm completion api request timeout (sec)

DEFAULT_TEMPERATURE = 0  # default temperature for LLM completion

LLM_PROVIDER_MODEL = getenv("LLM_PROVIDER_MODEL", "gpt4-o")


class LLMStreamer:
    def __init__(self):
        self.__openai_client = OpenAI(
            api_key=getenv("LLM_PROVIDER_API_KEY")
        )

    def ping(self, system_p, user_p, max_tokens, temperature):
        max_tokens = min(max_tokens, ALLOWED_MAX_OUT_TOKENS)
        return self.__openai_client.chat.completions.create(
            model=getenv("LLM_PROVIDER_MODEL"),
            messages=[
                {"role": "system", "content": system_p},
                {"role": "user", "content": user_p},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=LLM_PING_TIMEOUT,
            stream=True,
        )
