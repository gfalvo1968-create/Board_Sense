# routes/board_confidence.py

def calculate_confidence(score):
    """
    Convert the Board Sense score into a confidence percentage.
    """

    if score >= 10:
        return 90

    if score >= 5:
        return 75

    return 50
