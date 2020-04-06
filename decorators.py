from time import perf_counter, strftime
from functools import wraps
from urllib.parse import urlparse


class Timer:
    def __init__(self, function, write=False):
        self.__name__ = function.__name__
        self.function = function

    def __call__(self, *args, **kwargs):
        try:
            start = perf_counter()
            self.value = self.function(*args, **kwargs)
            self.elapsed = float(f"{(perf_counter() - start):.2f}")
            self.string_elapsed = f"finished in: {self.elapsed}s"
            self.string = f"{self.function.__name__!r} {self.string_elapsed}"
            self.printer()
            return self.value
        except ConnectionError as e:
            print(e)
        except Exception as e:
            pass

    def printer(self):
        print(f"{self.string}{self.elapsed}")


class ResponseTimer(Timer):
    def printer(self):
        parsed = urlparse(self.value.url)
        # print(parsed)
        # endpoint = parsed.netloc
        endpoint = ""
        if parsed.path:
            endpoint += parsed.path
        if parsed.params:
            endpoint += parsed.params
        if parsed.query:
            endpoint += parsed.query
        endpoint = endpoint.replace("//", "/")
        print(
            f"{strftime('[%d/%m/%Y %H:%M:%S]')} {self.value.status_code}@{endpoint!r} {self.string_elapsed} ")


def conditional_decorator(decoration, member):
    def decorator(method):
        predecorated = decoration(method)
        @wraps(method)
        def wrapper(*args, **kwargs):
            self = args[0]
            condition = getattr(self, member)
            if not condition:
                return method(*args, **kwargs)
            return predecorated(*args, **kwargs)
        return wrapper
    return decorator
