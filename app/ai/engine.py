from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest

FEATURES = [
    "temperature",
    "humidity",
    "delay_hours",
    "distance_km",
    "quality_score",
    "quantity_kg",
]


@dataclass
class RiskResult:
    score: int
    level: str
    reasons: list[str]
    importance: dict[str, float]
    predictive: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "reasons": self.reasons,
            "importance": self.importance,
            "predictive": self.predictive,
        }


class RiskEngine:
    """IsolationForest + transparent rules. Not random."""

    def __init__(self) -> None:
        rng = np.random.default_rng(42)
        n = 400
        normal = np.column_stack(
            [
                rng.normal(24.5, 1.6, n),
                rng.normal(62, 6, n),
                rng.normal(4, 2.5, n).clip(0, 20),
                rng.normal(80, 25, n).clip(10, 250),
                rng.normal(86, 6, n).clip(60, 100),
                rng.normal(1800, 400, n).clip(200, 4000),
            ]
        )
        self.model = IsolationForest(n_estimators=120, contamination=0.08, random_state=42)
        self.model.fit(normal)

    def assess(
        self,
        *,
        temperature: float,
        humidity: float,
        delay_hours: float,
        distance_km: float,
        quality_score: float,
        quantity_kg: float,
        route_deviation: bool = False,
        missing_events: int = 0,
    ) -> RiskResult:
        X = np.array([[temperature, humidity, delay_hours, distance_km, quality_score, quantity_kg]])
        iso = int(self.model.predict(X)[0] == -1)
        score = 8
        reasons: list[str] = []
        importance = {f: 0.0 for f in FEATURES}

        if temperature > 35 or temperature < 12:
            bump = 28 if temperature >= 80 else 18
            score += bump
            importance["temperature"] += bump
            reasons.append(f"Temperature exceeded safe threshold ({temperature:.1f}°C)")
        elif temperature > 30:
            score += 8
            importance["temperature"] += 8
            reasons.append(f"Temperature trending high ({temperature:.1f}°C)")

        if humidity > 80:
            score += 14
            importance["humidity"] += 14
            reasons.append(f"Humidity above safe envelope ({humidity:.1f}%)")
        elif humidity > 72:
            score += 6
            importance["humidity"] += 6

        if delay_hours > 24:
            score += 22
            importance["delay_hours"] += 22
            reasons.append(f"Delivery delayed by {delay_hours:.0f} hours")
        elif delay_hours > 12:
            score += 10
            importance["delay_hours"] += 10
            reasons.append(f"Moderate delay ({delay_hours:.0f} h)")

        if quality_score and quality_score < 70:
            score += 18
            importance["quality_score"] += 18
            reasons.append("Quality score decreased below passing grade")
        elif quality_score and quality_score < 80:
            score += 8
            importance["quality_score"] += 8

        if distance_km > 180:
            score += 6
            importance["distance_km"] += 6
        if quantity_kg > 4000:
            score += 4
            importance["quantity_kg"] += 4
        if route_deviation:
            score += 12
            reasons.append("Route deviation detected")
        if missing_events:
            score += min(15, missing_events * 5)
            reasons.append(f"{missing_events} required supply-chain events missing")
        if iso:
            score += 10
            reasons.append("Sensor pattern flagged by Isolation Forest")

        score = int(min(100, max(0, score)))
        if score >= 81:
            level = "CRITICAL"
        elif score >= 61:
            level = "HIGH"
        elif score >= 31:
            level = "MEDIUM"
        else:
            level = "LOW"

        if not reasons:
            reasons.append("Conditions within expected agricultural envelope")

        total = sum(importance.values()) or 1
        importance = {k: round(v / total, 3) for k, v in importance.items()}

        predictive = "Stable"
        if temperature > 32 and delay_hours > 8:
            predictive = "Spoilage risk likely to increase in the next 6–12 hours"
        elif score >= 61:
            predictive = "Intervene now — quality and cold-chain integrity at risk"

        return RiskResult(score, level, reasons, importance, predictive)


engine = RiskEngine()


def calculate_quality_score(moisture: float, foreign_matter: float) -> tuple[float, str, str]:
    score = 100 - max(0, moisture - 12) * 4 - foreign_matter * 8
    score = max(0, min(100, score))
    if score >= 88 and moisture <= 13 and foreign_matter <= 1.2:
        grade, status = "A", "PASSED"
    elif score >= 75:
        grade, status = "B", "PASSED"
    elif score >= 60:
        grade, status = "C", "HOLD"
    else:
        grade, status = "D", "FAILED"
    return round(score, 1), grade, status


def trust_score(
    *,
    origin_ok: bool,
    quality_ok: bool,
    chain_ok: bool,
    docs_ok: bool,
    sensors_ok: bool,
    completeness: float,
    ai_risk: float,
    delivery_ok: bool,
) -> tuple[int, dict[str, int]]:
    parts = {
        "origin": 15 if origin_ok else 0,
        "quality": 15 if quality_ok else 4,
        "blockchain": 20 if chain_ok else 0,
        "documents": 10 if docs_ok else 4,
        "sensors": 10 if sensors_ok else 3,
        "completeness": int(15 * completeness),
        "ai": int(10 * (1 - ai_risk / 100)),
        "delivery": 5 if delivery_ok else 1,
    }
    return min(100, sum(parts.values())), parts


def sustainability_score(distance_km: float, delay_hours: float, temp_deviation: float, wastage: float) -> dict[str, Any]:
    emissions = round(distance_km * 0.12, 2)  # kg CO2e estimate
    score = 92 - min(30, distance_km / 12) - min(20, delay_hours) - min(15, temp_deviation) - min(20, wastage)
    score = int(max(20, min(98, score)))
    reasons = []
    if distance_km < 100:
        reasons.append("Short route")
    if delay_hours < 6:
        reasons.append("Efficient transport")
    if wastage < 2:
        reasons.append("Low wastage")
    if temp_deviation < 3:
        reasons.append("Low temperature deviation")
    return {
        "score": score,
        "emissions_kg_co2e_estimate": emissions,
        "reasons": reasons or ["Baseline estimate"],
        "disclaimer": "Estimates only — not a certified carbon audit.",
    }
