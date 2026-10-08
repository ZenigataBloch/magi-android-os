from dataclasses import dataclass


@dataclass
class MAGIResult:

    agent: str
    decision: str
    confidence: float
    reasoning: str