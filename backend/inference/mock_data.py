"""Generate synthetic training data for the LSTM step classifier.

Creates simulated feature sequences that mimic:
- YOLO detection features (object counts + confidences)
- Hand keypoint features (21 landmarks x 3 coords x 2 hands)

Each SOP step has characteristic object/hand patterns that the LSTM can learn.
"""

import numpy as np

from backend.inference.feature_fusion import FUSED_FEATURE_SIZE, YOLO_CLASSES


def generate_step_sequence(
    step_id: int,
    num_classes: int,
    seq_len: int,
    feature_size: int = FUSED_FEATURE_SIZE,
    noise_level: float = 0.05,
) -> np.ndarray:
    """Generate a feature sequence for one SOP step.

    Each step has a distinct pattern of detected objects and hand positions.
    """
    features = np.random.randn(seq_len, feature_size).astype(np.float32) * noise_level

    # Define characteristic objects per step (indices into YOLO_CLASSES)
    class_to_idx = {name: i for i, name in enumerate(YOLO_CLASSES)}
    step_patterns = {
        0: ["person", "box"],           # preparing materials
        1: ["person", "bowl"],          # placing components
        2: ["person", "scissors"],      # cutting/assembling
        3: ["person", "bottle"],        # applying adhesive/testing
        4: ["person", "clock"],         # final check
    }

    pattern_objects = step_patterns.get(step_id % len(step_patterns), ["person"])

    # Set YOLO features: high counts and confidences for pattern objects
    for obj_name in pattern_objects:
        idx = class_to_idx.get(obj_name)
        if idx is not None:
            count_idx = idx * 2
            conf_idx = count_idx + 1
            features[:, count_idx] = np.random.poisson(2, seq_len).astype(np.float32)
            features[:, conf_idx] = np.clip(
                np.random.normal(0.8, 0.1, seq_len), 0.5, 1.0
            ).astype(np.float32)

    # Set hand features: varying hand positions per step
    hand_offset = len(YOLO_CLASSES) * 2
    # Each step has a characteristic hand position range
    hand_center = np.random.randn(126).astype(np.float32) * 0.3 + step_id * 0.5
    features[:, hand_offset:hand_offset + 126] += hand_center

    return features


def generate_training_data(
    num_classes: int = 5,
    samples_per_class: int = 100,
    seq_len_range: tuple[int, int] = (16, 48),
    feature_size: int = FUSED_FEATURE_SIZE,
) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Generate training dataset.

    Returns:
        (sequences_padded, labels, seq_lengths)
        sequences_padded: (total_samples, max_seq_len, feature_size)
        labels: (total_samples,)
        seq_lengths: list of actual sequence lengths
    """
    all_sequences = []
    all_labels = []
    all_lengths = []

    for class_id in range(num_classes):
        for _ in range(samples_per_class):
            seq_len = np.random.randint(*seq_len_range)
            seq = generate_step_sequence(class_id, num_classes, seq_len, feature_size)
            all_sequences.append(seq)
            all_labels.append(class_id)
            all_lengths.append(seq_len)

    # Pad sequences to max length
    max_len = max(all_lengths)
    padded = np.zeros((len(all_sequences), max_len, feature_size), dtype=np.float32)
    for i, seq in enumerate(all_sequences):
        padded[i, :len(seq)] = seq

    return padded, np.array(all_labels, dtype=np.int64), all_lengths


def generate_sop_sequence(
    num_classes: int = 5,
    frames_per_step: int = 30,
    feature_size: int = FUSED_FEATURE_SIZE,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a complete SOP execution sequence (for inference testing).

    Returns:
        (features, step_labels)
        features: (total_frames, feature_size)
        step_labels: (total_frames,) - which step each frame belongs to
    """
    all_features = []
    all_labels = []

    for step_id in range(num_classes):
        seq = generate_step_sequence(step_id, num_classes, frames_per_step, feature_size)
        all_features.append(seq)
        all_labels.extend([step_id] * frames_per_step)

    return np.concatenate(all_features), np.array(all_labels, dtype=np.int64)
