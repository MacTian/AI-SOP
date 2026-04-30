"""Hand keypoint extraction using MediaPipe HandLandmarker."""

import logging
import numpy as np

logger = logging.getLogger(__name__)

# 21 landmarks per hand, each with x, y, z
LANDMARKS_PER_HAND = 21
COORDS_PER_LANDMARK = 3
HAND_FEATURE_SIZE = LANDMARKS_PER_HAND * COORDS_PER_LANDMARK  # 63
MAX_HANDS = 2
TOTAL_HAND_FEATURE_SIZE = MAX_HANDS * HAND_FEATURE_SIZE  # 126


class HandExtractor:
    """Extracts hand keypoints from frames using MediaPipe HandLandmarker."""

    def __init__(self, model_path: str | None = None, num_hands: int = 2):
        self._model_path = model_path or str(
            __import__("pathlib").Path(__file__).parent / "models" / "hand_landmarker.task"
        )
        self._num_hands = num_hands
        self._landmarker = None

    def load_model(self):
        """Initialize the MediaPipe HandLandmarker."""
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions
            from mediapipe.tasks.python.vision import (
                HandLandmarker,
                HandLandmarkerOptions,
                RunningMode,
            )

            options = HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=self._model_path),
                running_mode=RunningMode.IMAGE,
                num_hands=self._num_hands,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._landmarker = HandLandmarker.create_from_options(options)
            logger.info(f"HandLandmarker loaded from {self._model_path}")
        except Exception as e:
            logger.warning(f"Failed to load HandLandmarker: {e}")
            self._landmarker = None

    def extract(self, frame: np.ndarray) -> np.ndarray:
        """Extract hand keypoints from a frame.

        Args:
            frame: BGR image as numpy array (H, W, 3)

        Returns:
            Feature vector of shape (TOTAL_HAND_FEATURE_SIZE,) = (126,).
            Zeros if no hands detected or model not loaded.
        """
        if self._landmarker is None:
            return np.zeros(TOTAL_HAND_FEATURE_SIZE, dtype=np.float32)

        try:
            import mediapipe as mp

            # Convert BGR to RGB
            rgb = frame[:, :, ::-1].copy()
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            result = self._landmarker.detect(mp_image)

            features = np.zeros(TOTAL_HAND_FEATURE_SIZE, dtype=np.float32)

            for hand_idx, landmarks in enumerate(result.hand_landmarks[:MAX_HANDS]):
                offset = hand_idx * HAND_FEATURE_SIZE
                for lm_idx, lm in enumerate(landmarks):
                    idx = offset + lm_idx * COORDS_PER_LANDMARK
                    features[idx] = lm.x
                    features[idx + 1] = lm.y
                    features[idx + 2] = lm.z

            return features

        except Exception as e:
            logger.debug(f"Hand extraction error: {e}")
            return np.zeros(TOTAL_HAND_FEATURE_SIZE, dtype=np.float32)

    @staticmethod
    def feature_size() -> int:
        """Return the size of the feature vector."""
        return TOTAL_HAND_FEATURE_SIZE
