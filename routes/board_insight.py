"""
board_insight.py

Board Sense Insight Engine

Purpose:
Transform analysis results into clear, useful explanations
for the user.

Foundation:
Answers inform.
Insight transforms.
"""

from typing import Dict, List


class BoardInsight:

    def generate(self, analysis: Dict) -> Dict:
        """
        Generate a human-readable insight report.
        """

        insight = {
            "summary": self._summary(analysis),
            "evidence": self._evidence(analysis),
            "recommendation": self._recommendation(analysis),
            "confidence_reason": self._confidence_reason(analysis),
            "next_steps": self._next_steps(analysis)
        }

        return insight

    def _evidence(self, analysis):
    evidence = []

    for feature, detected in analysis.get("features", {}).items():
        if detected:
            evidence.append(feature)

    return evidence

    def _evidence(self, analysis):

        evidence = []

       evidence = []

for feature, detected in analysis.get("features", {}).items():
    if detected:
        evidence.append(feature)

return evidence

        return evidence

    def _recommendation(self, analysis):

        return analysis.get(
            "recommendation",
            "Further inspection recommended."
        )

    def _confidence_reason(self, analysis):

        confidence = analysis.get("confidence", 0)

        if confidence >= 90:
            return "Multiple visual and knowledge matches support this result."

        if confidence >= 75:
            return "Several strong indicators were detected."

        return "Limited evidence. Additional images may improve confidence."

    def _next_steps(self, analysis):

        return analysis.get("next_steps", [])
