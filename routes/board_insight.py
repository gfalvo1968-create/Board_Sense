"""
Board Sense Insight Engine

Converts board analysis into a human-readable report.
"""

from typing import Dict, List


class BoardInsight:

    def generate(self, analysis: Dict) -> Dict:
        return {
            "summary": self._summary(analysis),
            "board_type": analysis.get("board_type", "General PCB"),
            "board_type_reason": analysis.get(
                "board_type_reason",
                "No stronger board-type pattern has been confirmed yet.",
            ),
            "evidence": self._evidence(analysis),
            "recommendation": self._recommendation(analysis),
            "confidence_reason": self._confidence_reason(analysis),
            "next_steps": self._next_steps(analysis),
        }

    def _summary(self, analysis: Dict) -> str:
        grade = analysis.get("grade", "Unknown")
        score = analysis.get("score", 0)
        confidence = analysis.get("confidence", 0)
        board_type = analysis.get("board_type", "General PCB")

        return (
            f"{board_type} classified as {grade} with a recovery score of "
            f"{score} and {confidence}% confidence."
        )

    def _evidence(self, analysis: Dict) -> List[str]:
        evidence = []
        seen = set()

        features = analysis.get("features", {})
        visual = analysis.get("visual", {})
        signals = analysis.get("signals", {})
        power = analysis.get("power", {})

        labels = {
            "motherboard": "Motherboard characteristics detected",
            "ram": "RAM / memory-module characteristics detected",
            "memory_module": "Memory-module form detected",
            "gold_fingers": "Gold-bearing edge connector detected",
            "large_ic_chips": "Multiple large IC-like packages detected",
            "dense_component_board": "Dense component population detected",
            "processor": "Large central processor-like package detected",
            "power_board": "Power-board characteristics detected",
            "possible_ram": "Long, narrow RAM-like geometry",
            "gold_finger_edge": "Gold-colored material detected near board edge",
            "possible_large_ic_chips": "Visual detector found large IC-like regions",
            "possible_motherboard": "Motherboard-like size and proportions",
            "large_board": "Large board geometry detected",
            "possible_power_board": "Power-board geometry and component pattern detected",
            "sparse_component_layout": "Sparse layout with larger power-style components",
        }

        for source in (features, visual, signals, power):
            for key, value in source.items():
                if value is True:
                    text = labels.get(key, key.replace("_", " ").title())
                    if text not in seen:
                        evidence.append(text)
                        seen.add(text)

        component_count = int(features.get("component_count", 0) or 0)
        if component_count:
            evidence.append(f"{component_count} chip-like component regions detected")

        component_density = float(features.get("component_density", 0) or 0)
        if component_density > 0:
            evidence.append(
                f"Chip-like component coverage: {component_density * 100:.1f}%"
            )

        gold_ratio = float(visual.get("gold_ratio", 0) or 0)
        if gold_ratio > 0:
            evidence.append(f"Edge gold-color ratio: {gold_ratio * 100:.1f}%")

        aspect_ratio = float(visual.get("aspect_ratio", 0) or 0)
        if aspect_ratio > 0:
            evidence.append(f"Board aspect ratio: {aspect_ratio:.2f}:1")

        round_components = int(power.get("large_round_components", 0) or 0)
        if round_components:
            evidence.append(f"{round_components} large round component regions detected")

        power_score = int(power.get("power_score", 0) or 0)
        if power_score:
            evidence.append(f"Power-board evidence score: {power_score}/8")

        if not evidence:
            evidence.append("No strong recovery indicators detected from this image")

        return evidence

    def _recommendation(self, analysis: Dict) -> str:
        return analysis.get(
            "recommendation",
            "Further inspection recommended."
        )

    def _confidence_reason(self, analysis: Dict) -> str:
        confidence = analysis.get("confidence", 0)

        if confidence >= 90:
            return "High confidence based on multiple agreeing visual indicators."

        if confidence >= 75:
            return "Good confidence based on several matching board characteristics."

        if confidence >= 50:
            return (
                "Moderate confidence. A second image or closer component view "
                "could improve accuracy."
            )

        return "Low confidence. More visual information is recommended."

    def _next_steps(self, analysis: Dict) -> List[str]:
        grade = analysis.get("grade", "LOW")
        features = analysis.get("features", {})
        board_type = analysis.get("board_type", "General PCB")
        steps = []

        if grade == "HIGH":
            steps.extend([
                "Separate this board from general e-waste.",
                "Inspect high-value ICs and edge connectors before processing.",
            ])
        elif grade == "MEDIUM":
            steps.extend([
                "Separate for later evaluation.",
                "Inspect valuable chips and connector areas before selling.",
            ])
        else:
            steps.extend([
                "Process with general e-waste unless manual inspection finds value.",
                "Recover reusable components only when practical.",
            ])

        if "Power" in board_type:
            steps.append("Inspect transformers, coils, heat sinks, and large capacitors separately.")
        if features.get("processor"):
            steps.append("Inspect the processor-like package separately.")
        if features.get("gold_fingers"):
            steps.append("Check the edge connector for recoverable gold-bearing contacts.")
        if features.get("large_ic_chips"):
            steps.append("Review the larger IC packages before bulk processing.")

        return steps
