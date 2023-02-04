import importlib
import traceback

from galacteek import log
from galacteek.config import cGet


def apimod():
    try:
        return importlib.import_module('openai')
    except Exception as err:
        log.warning(f'The openai library was not found: {err}')


def setApiKey(apiKey: str):
    openai = apimod()

    if openai:
        openai.api_key = apiKey


def reconfigure(apiKey: str):
    if 0:
        apiKey = cGet('openai.accounts.main.apiKey',
                      mod='galacteek.ai.openai')

    if apiKey:
        setApiKey(apiKey)


async def complete(prompt: str,
                   engine: str = 'text-davinci-003',
                   maxtokens: int = 100,
                   temperature: int = -1):
    account = cGet('accounts.main',
                   mod='galacteek.ai.openai')

    try:
        openai = apimod()

        completion = await openai.Completion.acreate(
            engine=engine,
            prompt=prompt,
            max_tokens=maxtokens,
            n=1,
            stop=None,
            temperature=account.params.temperature
        )
    except Exception:
        log.debug(traceback.format_exc())
    else:
        return completion
