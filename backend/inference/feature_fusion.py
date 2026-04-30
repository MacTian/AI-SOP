"""Feature fusion: combines YOLO detection features + hand keypoint features."""

import logging
import numpy as np

from backend.inference.detector import DetectionResult
from backend.inference.hand_extractor import TOTAL_HAND_FEATURE_SIZE

logger = logging.getLogger(__name__)

# YOLO feature: per-class detection counts + avg confidences
# We'll use a fixed set of common classes (COCO subset) for consistency
YOLO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]
YOLO_FEATURE_SIZE = len(YOLO_CLASSES) * 2  # count + avg_conf per class
FUSED_FEATURE_SIZE = YOLO_FEATURE_SIZE + TOTAL_HAND_FEATURE_SIZE


def extract_yolo_features(detection_result: DetectionResult) -> np.ndarray:
    """Convert YOLO detections into a fixed-size feature vector.

    For each class: (detection_count, average_confidence).
    Shape: (YOLO_FEATURE_SIZE,)
    """
    class_to_idx = {name: i for i, name in enumerate(YOLO_CLASSES)}
    counts = np.zeros(len(YOLO_CLASSES), dtype=np.float32)
    conf_sums = np.zeros(len(YOLO_CLASSES), dtype=np.float32)

    for det in detection_result.detections:
        idx = class_to_idx.get(det.class_name)
        if idx is not None:
            counts[idx] += 1
            conf_sums[idx] += det.confidence

    # Average confidence (avoid division by zero)
    avg_confs = np.where(counts > 0, conf_sums / counts, 0.0)

    # Interleave: [count_0, conf_0, count_1, conf_1, ...]
    features = np.empty(YOLO_FEATURE_SIZE, dtype=np.float32)
    features[0::2] = counts
    features[1::2] = avg_confs

    return features


def fuse_features(
    detection_result: DetectionResult,
    hand_features: np.ndarray,
) -> np.ndarray:
    """Fuse YOLO detection features and hand keypoint features.

    Returns:
        Fused feature vector of shape (FUSED_FEATURE_SIZE,).
    """
    yolo_feat = extract_yolo_features(detection_result)
    return np.concatenate([yolo_feat, hand_features])


def feature_size() -> int:
    """Return the total fused feature size."""
    return FUSED_FEATURE_SIZE
