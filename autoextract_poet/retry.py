"""
AutoExtract additional retrying logic to the one
provided by tha AutoExtract client.

The general policy is:

* No retry on deterministic errors (e.g. Wrong API key, malformed query, etc)
* Retry when there are chances to obtain a different response
  (e.g. after query timeout or in the presence of HTTP 500 from target site)
* Retry after the suggested time for the "domain is occupied ..." case

See https://doc.scrapinghub.com/autoextract.html#errors

"""
import logging
import re
from typing import Optional

from tenacity import (
    RetryCallState,
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_delay,
    wait_fixed,
    wait_random,
    wait_random_exponential,
)
from tenacity.stop import stop_base, stop_never
from tenacity.wait import wait_base

from autoextract_poet.exceptions import QueryLevelError

logger = logging.getLogger(__name__)

_DOMAIN_OCCUPIED_RE = re.compile(
    r".*domain .* is occupied, please retry in (.*) seconds.*", re.IGNORECASE
)


def _domain_occupied(msg: Optional[str]) -> Optional[float]:
    """
    >>> _domain_occupied(" Domain blablabla is occupied, please retry in 23.5 seconds ")
    23.5
    >>> _domain_occupied(" Domain blablabla is occupied, please retry in sfbe seconds ")
    300
    >>> _domain_occupied(" domain blablabla is occupied, please retry in 5 seconds ")
    5.0
    >>> _domain_occupied(" domain blablabla is occupied, please retry in 5 seconds ")
    5.0
    >>> _domain_occupied("hi")
    """
    match = _DOMAIN_OCCUPIED_RE.match(msg or "")
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            logger.warning(
                f"Received a malformed occupied error message :{msg}. "
                f"Retying after 5 minutes."
            )
            return 60 * 5


def _is_domain_occupied_error(exc: Exception) -> Optional[float]:
    if isinstance(exc, QueryLevelError):
        return _domain_occupied(exc.msg)


_RETRIABLE_ERR_MSGS = {
    msg.lower().strip()
    for msg in [
        "query timed out",
        "Downloader error: No response (network5)",
        "Downloader error: http50",
        "Downloader error: GlobalTimeoutError",
        "Proxy error: banned",
        "Proxy error: internal_error",
        "Proxy error: nxdomain",
        "Proxy error: timeout",
        "Proxy error: ssl_tunnel_error",
        "Proxy error: msgtimeout",
        "Proxy error: econnrefused",
    ]
}

# Retry errors for AutoExtract API dev server
_RETRIABLE_ERR_MSGS.update(
    {
        msg.lower().strip()
        for msg in [
            "Error making splash request: ServerDisconnectedError",
            "Error making splash request: ClientOSError: [Errno 32] Broken pipe",
        ]
    }
)


def _is_retriable_error_msg(msg: Optional[str]):
    """
    >>> _is_retriable_error_msg(" query timed Out ")
    True
    >>> _is_retriable_error_msg("ey")
    False
    >>> _is_retriable_error_msg(None)
    False
    """
    msg = msg or ""
    return msg.lower().strip() in _RETRIABLE_ERR_MSGS


def _is_retriable_error(exc: Exception):
    if isinstance(exc, QueryLevelError):
        return _is_retriable_error_msg(exc.msg)


autoextract_retry_condition = retry_if_exception(
    _is_domain_occupied_error
) | retry_if_exception(_is_retriable_error)


class autoextract_wait_strategy(wait_base):
    def __init__(self):
        self.retriable_wait = (
            # wait from 3s to ~1m
            wait_random(3, 7)
            + wait_random_exponential(multiplier=1, max=55)
        )

    def __call__(self, retry_state: RetryCallState) -> float:
        exc = retry_state.outcome.exception()
        wait = _is_domain_occupied_error(exc)
        if wait:
            return wait_fixed(wait)
        elif _is_retriable_error(exc):
            return self.retriable_wait(retry_state=retry_state)
        else:
            raise RuntimeError("Invalid retry state exception: %s" % exc)


class autoextract_stop_strategy(stop_base):
    def __init__(self):
        self.stop_on_15_minutes = stop_after_delay(15 * 60)

    def __call__(self, retry_state: RetryCallState) -> bool:
        exc = retry_state.outcome.exception()
        if _is_domain_occupied_error(exc):
            return stop_never
        elif _is_retriable_error(exc):
            return self.stop_on_15_minutes(retry_state)
        else:
            raise RuntimeError("Invalid retry state exception: %s" % exc)


autoextract_retry = retry(
    wait=autoextract_wait_strategy(),
    retry=autoextract_retry_condition,
    stop=autoextract_stop_strategy(),
    before_sleep=before_sleep_log(logger, logging.DEBUG),
    after=after_log(logger, logging.DEBUG),
)
