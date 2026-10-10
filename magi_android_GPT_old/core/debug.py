from config import DEBUG


def dbg(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)