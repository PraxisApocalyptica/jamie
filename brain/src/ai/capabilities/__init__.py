from .movement import Movement
from .perception import Perception
from .cognition import Cognition


CAPABILITIES = [cls for cls in [
    Movement,
    Perception,
    Cognition,
] if cls is not None]

# You could also add other exports here if needed later
__all__ = ['Movement', 'Perception', 'Cognition', 'CAPABILITIES']
