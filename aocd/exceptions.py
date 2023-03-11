class AocdError(Exception):
    """base exception for this package"""


class PuzzleLockedError(AocdError):
    """trying to access input before the unlock"""


class PuzzleUnsolvedError(AocdError):
    """answer is unknown because user has not solved puzzle yet"""


class DeadTokenError(AocdError):
    """the auth is expired/incorrect"""


class UnknownUserError(AocdError):
    """the token for this userid was not found in the cache"""
