# helpers/utils.py
import functools, time, logging
logger = logging.getLogger("utils")

def retry(exceptions=(Exception,), tries=4, delay=1, backoff=2):
    def deco(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except exceptions as e:
                    logger.warning("Retryable error %s, retrying in %s s (%s tries left)", e, mdelay, mtries-1)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)
        return wrapper
    return deco
