"""Secret masking contract shared by the ported providers and settings API."""
MASK = "********"


def has_real_model_api_key(value):
    return isinstance(value, str) and bool(value.strip()) and set(value.strip()) != {"*"}


class EmptyModelResponseError(Exception):
    pass
