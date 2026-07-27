"""
Board Sense Insight Engine

Converts board analysis into a human-readable report.
"""

from typing import Dict, List


class BoardInsight:

    def generate(self, analysis: Dict) -> Dict:
        return {
            "summary": self._summary(analysis),
            "evidence": self._evidence(analysis),
            "recommendation": self._recommendation(analysis),
            "confidence_reason": self._confidence_reason(analysis),
            "next_steps": self._next_steps(analysis),
        }

    def _summary(self, analysis: Dict) -> str:
        grade = analysis.get("grade", "Unknown")
        score = analysis.get("score", 0)

        return (
            f"Board classified as {grade} "
            f"with a recovery score of {score}."
        )

    def _evidence(self, analysis: Dict) -> List[str]:
        evidence = []

        features = analysis.get("features", {})
        visual = analysis.get("visual", {})
        signals = analysis.get("signals", {})

        for key, value in features.items():
            if value:
                evidence.append(key.replace("_", " ").title())

        for key, value in visual.items():
            if value:
                evidence.append(key.replace("_", " ").title())

        for key, value in signals.items():
            if value:
                evidence.append(key.replace("_", " ").title())

        return evidence

    def _recommendation(self, analysis: Dict) -> str:
        return analysis.get(
            "recommendation",
            "Further inspection recommended."
        )

    def _confidence_reason(self, analysis: Dict) -> str:
        confidence = analysis.get("confidence", 0)

        if confidence >= 0.90:
            return (
                "High confidence based on multiple visual "
                "and feature indicators."
            )

        if confidence >= 0.75:
            return (
                "Good confidence based on several matching "
                "board characteristics."
            )

        if confidence >= 0.50:
            return (
                "Moderate confidence. Additional images "
                "could improve accuracy."
            )

        return (
            "Low confidence. More information is recommended."
        )

    def _next_steps(self, analysis: Dict) -> List[str]:

        grade = analysis.get("grade", "LOW")

        if grade == "HIGH":
            return [
                "Separate this board.",
                "Inspect for CPUs and RAM.",
                "Recover gold-bearing components.",
                "Store with premium boards."
            ]

        if grade == "MEDIUM":
            return [
                "Separate for later processing.",
                "Inspect valuable chips.",
                "Evaluate before selling."
            ]

        return [
            "Process with general e-waste.",
            "Recover reusable components if practical."
        ]
