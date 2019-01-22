class AocdError(Exception):
    """base exception for this package"""


class PuzzleUnsolvedError(AocdError):
    """answer is unknown because user has not solved puzzle yet"""
