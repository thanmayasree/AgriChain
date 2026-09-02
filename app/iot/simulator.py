from __future__ import annotations

import time
from typing import Any

import numpy as np


class IoTSimulator:
    def __init__(self, seed: int = 42) -> None:
        self.rng = np.random.default_rng(seed)
        self.tick = 0

    def reading(
        self,
        *,
        batch_id: str,
        lat: float = 16.55,
        lng: float = 82.0,
        spike: bool = False,
    ) -> dict[str, Any]:
        self.tick += 1
        temp = 25.2 + 0.15 * (self.tick % 8) + float(self.rng.normal(0, 0.25))
        if spike:
            temp = 89.0
        humidity = 65 + float(self.rng.normal(0, 1.2))
        speed = max(0, float(self.rng.normal(38, 4)))
        vibration = abs(float(self.rng.normal(0.4, 0.15)))
        lat += float(self.rng.normal(0, 0.004))
        lng += float(self.rng.normal(0, 0.004))
        return {
            "batch_id": batch_id,
            "temperature": round(temp, 2),
            "humidity": round(humidity, 2),
            "lat": round(lat, 5),
            "lng": round(lng, 5),
            "speed_kmh": round(speed, 1),
            "vibration": round(vibration, 3),
            "timestamp": time.time(),
        }


simulator = IoTSimulator()
