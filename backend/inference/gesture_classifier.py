"""Gesture classifier: recognizes hand gestures from MediaPipe landmarks.

Supported gestures:
- grab: fingers curled into fist (fingertips close to palm center)
- point: index finger extended, other fingers curled
- pick_up: hand moving upward with fingers closing (grab + upward motion)
- put_down: hand moving downward with fingers opening (release + downward motion)

Uses geometric relationships between 21 hand landmarks (no ML needed).
"""

import logging
from dataclasses import dataclass
from collections import deque

import numpy as np

logger = logging.getLogger(__name__)

# MediaPipe hand landmark indices
WRIST = 0
THUMB_TIP = 4
THUMB_IP = 3
THUMB_MCP = 2
INDEX_TIP = 8
INDEX_DIP = 7
INDEX_PIP = 6
INDEX_MCP = 5
MIDDLE_TIP = 12
MIDDLE_DIP = 11
MIDDLE_PIP = 10
MIDDLE_MCP = 9
RING_TIP = 16
RING_DIP = 15
RING_PIP = 14
RING_MCP = 13
PINKY_TIP = 20
PINKY_DIP = 19
PINKY_PIP = 18
PINKY_MCP = 17

# Palm center landmarks (average of MCP joints)
PALM_LANDMARKS = [WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]

# Fingertip and PIP pairs for curl detection
FINGER_PAIRS = [
    (INDEX_TIP, INDEX_PIP),
    (MIDDLE_TIP, MIDDLE_PIP),
    (RING_TIP, RING_PIP),
    (PINKY_TIP, PINKY_PIP),
]

GESTURE_NAMES = ["grab", "point", "pick_up", "put_down", "open", "unknown"]


@dataclass
class GestureResult:
    """Gesture classification result."""
    gesture: str  # one of GESTURE_NAMES
    confidence: float
    hand_index: int  # 0 or 1
    # Raw metrics for debugging
    finger_curl: float = 0.0  # 0=open, 1=fully curled
    y_velocity: float = 0.0  # positive=up, negative=down


class GestureClassifier:
    """Classifies hand gestures from MediaPipe landmark sequences.

    Uses geometric heuristics (no ML), with temporal smoothing via a
    sliding window of recent poses.
    """

    def __init__(
        self,
        history_size: int = 8,
        grab_threshold: float = 0.55,
        point_threshold: float = 0.5,
        velocity_threshold: float = 0.015,
    ):
        self.history_size = history_size
        self.grab_threshold = grab_threshold
        self.point_threshold = point_threshold
        self.velocity_threshold = velocity_threshold

        # Per-hand history: list of (finger_curl, wrist_y) tuples
        self._history: dict[int, deque] = {}

    def reset(self):
        """Clear gesture history."""
        self._history.clear()

    def classify(self, hand_features: np.ndarray, hand_index: int = 0) -> GestureResult:
        """Classify gesture from a single hand's landmark features.

        Args:
            hand_features: Flattened (63,) array of 21 landmarks x (x, y, z).
                           Values in [0, 1] range (MediaPipe normalized coords).
            hand_index: Which hand (0 or 1)

        Returns:
            GestureResult with detected gesture
        """
        if hand_features.size < 63:
            return GestureResult("unknown", 0.0, hand_index)

        # Reshape to (21, 3)
        landmarks = hand_features[:63].reshape(21, 3)

        # Check if hand is actually present (non-zero)
        if np.allclose(landmarks, 0, atol=1e-6):
            return GestureResult("unknown", 0.0, hand_index)

        # Compute finger curl metric
        finger_curl = self._compute_finger_curl(landmarks)

        # Get wrist Y for velocity tracking
        wrist_y = landmarks[WRIST, 1]

        # Update history
        if hand_index not in self._history:
            self._history[hand_index] = deque(maxlen=self.history_size)
        self._history[hand_index].append((finger_curl, wrist_y))

        # Compute vertical velocity from history
        y_velocity = self._compute_y_velocity(hand_index)

        # Classify gesture
        gesture, confidence = self._classify_pose(
            landmarks, finger_curl, y_velocity
        )

        return GestureResult(
            gesture=gesture,
            confidence=round(confidence, 3),
            hand_index=hand_index,
            finger_curl=round(finger_curl, 3),
            y_velocity=round(y_velocity, 4),
        )

    def classify_both_hands(self, features: np.ndarray) -> list[GestureResult]:
        """Classify gestures for both hands from the full 126-dim feature vector.

        Args:
            features: (126,) array = hand_0 (63,) + hand_1 (63,)

        Returns:
            List of GestureResult for each detected hand
        """
        results = []
        for i in range(2):
            start = i * 63
            hand_feat = features[start:start + 63]
            if not np.allclose(hand_feat, 0, atol=1e-6):
                results.append(self.classify(hand_feat, hand_index=i))
        return results

    def _compute_finger_curl(self, landmarks: np.ndarray) -> float:
        """Compute average finger curl (0=fully open, 1=fully closed).

        Compares fingertip distance to palm center vs PIP distance to palm center.
        """
        palm_center = np.mean(landmarks[PALM_LANDMARKS, :2], axis=0)

        curls = []
        for tip_idx, pip_idx in FINGER_PAIRS:
            tip_dist = np.linalg.norm(landmarks[tip_idx, :2] - palm_center)
            pip_dist = np.linalg.norm(landmarks[pip_idx, :2] - palm_center)
            if pip_dist > 1e-6:
                # If tip is closer to palm than PIP, finger is curled
                curl = max(0, 1.0 - tip_dist / pip_dist)
                curls.append(curl)

        # Also check thumb
        thumb_tip_dist = np.linalg.norm(landmarks[THUMB_TIP, :2] - palm_center)
        thumb_mcp_dist = np.linalg.norm(landmarks[THUMB_MCP, :2] - palm_center)
        if thumb_mcp_dist > 1e-6:
            thumb_curl = max(0, 1.0 - thumb_tip_dist / thumb_mcp_dist)
            curls.append(thumb_curl)

        return float(np.mean(curls)) if curls else 0.0

    def _compute_y_velocity(self, hand_index: int) -> float:
        """Compute vertical velocity from wrist Y history.

        Negative velocity = hand moving down (Y increases downward in image coords).
        Positive velocity = hand moving up.
        """
        history = self._history.get(hand_index)
        if history is None or len(history) < 3:
            return 0.0

        # Use last few frames to compute velocity
        recent = list(history)[-4:]
        y_values = [y for _, y in recent]

        # Simple linear regression slope
        n = len(y_values)
        if n < 2:
            return 0.0

        # Average difference (negate because image Y is inverted)
        diffs = [y_values[i] - y_values[i - 1] for i in range(1, n)]
        avg_diff = sum(diffs) / len(diffs)

        # Negative diff = wrist moved down in image = hand moving down
        # We want: positive = up, negative = down
        return -avg_diff

    def _classify_pose(
        self,
        landmarks: np.ndarray,
        finger_curl: float,
        y_velocity: float,
    ) -> tuple[str, float]:
        """Classify gesture from current pose metrics.

        Priority order:
        1. pick_up: grab + moving up
        2. put_down: open + moving down
        3. grab: fingers curled
        4. point: index extended, others curled
        5. open: all fingers extended
        6. unknown: ambiguous
        """
        # Check index finger extension vs others (for "point")
        index_extended = self._is_finger_extended(landmarks, INDEX_TIP, INDEX_PIP, INDEX_MCP)
        middle_curled = not self._is_finger_extended(landmarks, MIDDLE_TIP, MIDDLE_PIP, MIDDLE_MCP)
        ring_curled = not self._is_finger_extended(landmarks, RING_TIP, RING_PIP, RING_MCP)
        pinky_curled = not self._is_finger_extended(landmarks, PINKY_TIP, PINKY_PIP, PINKY_MCP)

        is_pointing = index_extended and middle_curled and ring_curled and pinky_curled

        # Motion detection
        is_moving_up = y_velocity > self.velocity_threshold
        is_moving_down = y_velocity < -self.velocity_threshold

        # Gesture classification
        # pick_up: grab + upward motion
        if finger_curl > self.grab_threshold and is_moving_up:
            return "pick_up", min(1.0, finger_curl + 0.2)

        # put_down: fingers opening + downward motion
        if finger_curl < 0.4 and is_moving_down:
            return "put_down", min(1.0, (1.0 - finger_curl) + 0.2)

        # grab: fingers curled
        if finger_curl > self.grab_threshold:
            return "grab", finger_curl

        # point: index extended, others curled
        if is_pointing:
            return "point", 0.8

        # open: all fingers extended
        all_extended = (
            index_extended
            and self._is_finger_extended(landmarks, MIDDLE_TIP, MIDDLE_PIP, MIDDLE_MCP)
            and self._is_finger_extended(landmarks, RING_TIP, RING_PIP, RING_MCP)
            and self._is_finger_extended(landmarks, PINKY_TIP, PINKY_PIP, PINKY_MCP)
        )
        if all_extended and finger_curl < 0.3:
            return "open", 1.0 - finger_curl

        return "unknown", 0.3

    def _is_finger_extended(
        self,
        landmarks: np.ndarray,
        tip_idx: int,
        pip_idx: int,
        mcp_idx: int,
    ) -> bool:
        """Check if a finger is extended (tip farther from wrist than PIP)."""
        wrist = landmarks[WRIST, :2]
        tip = landmarks[tip_idx, :2]
        pip = landmarks[pip_idx, :2]

        tip_dist = np.linalg.norm(tip - wrist)
        pip_dist = np.linalg.norm(pip - wrist)

        return tip_dist > pip_dist * 1.1  # 10% margin
