"""Tests for LSTM classifier, hand extractor, feature fusion, and training."""

import numpy as np
import torch

from backend.inference.hand_extractor import HandExtractor, TOTAL_HAND_FEATURE_SIZE
from backend.inference.feature_fusion import (
    extract_yolo_features,
    fuse_features,
    FUSED_FEATURE_SIZE,
    YOLO_FEATURE_SIZE,
)
from backend.inference.detector import DetectionResult, Detection
from backend.inference.lstm_classifier import (
    StepLSTM,
    MultiScaleVoter,
    create_model,
    save_model,
    load_model,
)
from backend.inference.mock_data import (
    generate_step_sequence,
    generate_training_data,
    generate_sop_sequence,
)
from backend.inference.lstm_trainer import LstmTrainer


# --- Hand Extractor ---

def test_hand_extractor_feature_size():
    assert HandExtractor.feature_size() == TOTAL_HAND_FEATURE_SIZE
    assert TOTAL_HAND_FEATURE_SIZE == 126  # 21 landmarks * 3 coords * 2 hands


def test_hand_extractor_no_model():
    """Without loading model, should return zeros."""
    ext = HandExtractor()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = ext.extract(frame)
    assert result.shape == (TOTAL_HAND_FEATURE_SIZE,)
    assert np.all(result == 0)


# --- Feature Fusion ---

def test_extract_yolo_features_empty():
    result = DetectionResult(detections=[])
    feat = extract_yolo_features(result)
    assert feat.shape == (YOLO_FEATURE_SIZE,)
    assert np.all(feat == 0)


def test_extract_yolo_features_with_detections():
    detections = [
        Detection(class_id=0, class_name="person", confidence=0.9, bbox=(0, 0, 100, 100)),
        Detection(class_id=0, class_name="person", confidence=0.8, bbox=(100, 100, 200, 200)),
        Detection(class_id=39, class_name="bottle", confidence=0.7, bbox=(50, 50, 80, 80)),
    ]
    result = DetectionResult(detections=detections)
    feat = extract_yolo_features(result)

    # person is at index 0: count=2, avg_conf=0.85
    assert feat[0] == 2.0  # count
    assert abs(feat[1] - 0.85) < 0.01  # avg confidence

    # bottle index: find it
    from backend.inference.feature_fusion import YOLO_CLASSES
    bottle_idx = YOLO_CLASSES.index("bottle")
    assert feat[bottle_idx * 2] == 1.0  # count
    assert abs(feat[bottle_idx * 2 + 1] - 0.7) < 0.01


def test_fuse_features():
    det_result = DetectionResult(detections=[])
    hand_feat = np.zeros(TOTAL_HAND_FEATURE_SIZE, dtype=np.float32)
    fused = fuse_features(det_result, hand_feat)
    assert fused.shape == (FUSED_FEATURE_SIZE,)


# --- LSTM Classifier ---

def test_lstm_forward():
    model = StepLSTM(input_size=FUSED_FEATURE_SIZE, hidden_size=64, num_classes=5)
    x = torch.randn(2, 16, FUSED_FEATURE_SIZE)
    out = model(x)
    assert out.shape == (2, 5)


def test_lstm_create_and_save_load(tmp_path):
    model = create_model(FUSED_FEATURE_SIZE, 64, 5)
    path = tmp_path / "test_model.pt"
    save_model(model, path, metadata={"test": True})

    loaded = load_model(path)
    assert loaded.lstm.input_size == FUSED_FEATURE_SIZE
    assert loaded.fc[-1].out_features == 5

    # Verify weights match
    for p1, p2 in zip(model.parameters(), loaded.parameters()):
        assert torch.allclose(p1, p2)


def test_multiscale_voter():
    model = create_model(FUSED_FEATURE_SIZE, 64, 5)
    voter = MultiScaleVoter(model, window_sizes=[4, 8, 12])

    # Not enough data
    pred, probs = voter.predict()
    assert pred == -1
    assert len(probs) == 5

    # Add features
    for _ in range(15):
        voter.add_feature(np.random.randn(FUSED_FEATURE_SIZE).astype(np.float32))

    pred, probs = voter.predict()
    assert 0 <= pred < 5
    assert len(probs) == 5
    assert abs(sum(probs) - 1.0) < 0.01


def test_multiscale_voter_reset():
    model = create_model(FUSED_FEATURE_SIZE, 64, 5)
    voter = MultiScaleVoter(model, window_sizes=[4])
    voter.add_feature(np.random.randn(FUSED_FEATURE_SIZE).astype(np.float32))
    assert voter.buffer_size() == 1
    voter.reset()
    assert voter.buffer_size() == 0


# --- Mock Data ---

def test_generate_step_sequence():
    seq = generate_step_sequence(0, 5, 20)
    assert seq.shape == (20, FUSED_FEATURE_SIZE)


def test_generate_training_data():
    X, y, lengths = generate_training_data(num_classes=3, samples_per_class=10)
    assert X.shape[0] == 30  # 3 * 10
    assert len(y) == 30
    assert len(lengths) == 30
    assert set(y.tolist()) == {0, 1, 2}


def test_generate_sop_sequence():
    features, labels = generate_sop_sequence(num_classes=5, frames_per_step=20)
    assert features.shape == (100, FUSED_FEATURE_SIZE)
    assert len(labels) == 100
    assert list(labels[:20]).count(0) == 20
    assert list(labels[20:40]).count(1) == 20


# --- LSTM Trainer ---

def test_lstm_trainer():
    trainer = LstmTrainer(num_classes=3, epochs=3, hidden_size=32, batch_size=16)
    assert not trainer.is_training

    result = trainer.train()
    assert result["status"] == "completed"
    assert result["epochs"] == 3
    assert result["final_accuracy"] > 0  # Should learn something
    assert len(result["history"]) == 3

    status = trainer.get_status()
    assert not status["is_training"]
    assert len(status["history"]) == 3
