"""LSTM-based action step classifier with multi-scale temporal windows."""

import logging
import os
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "models"


class StepLSTM(nn.Module):
    """LSTM classifier for SOP step recognition.

    Input: sequence of fused feature vectors (batch, seq_len, input_size)
    Output: class probabilities (batch, num_classes)
    """

    def __init__(self, input_size: int, hidden_size: int, num_classes: int, num_layers: int = 2, dropout: float = 0.3):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, input_size)
        lstm_out, _ = self.lstm(x)
        # Use last time step output
        last_output = lstm_out[:, -1, :]
        return self.fc(last_output)


class MultiScaleVoter:
    """Multi-scale temporal window voting for stable step prediction.

    Maintains feature buffers at multiple window sizes and fuses predictions
    by averaging probabilities across scales.
    """

    def __init__(
        self,
        model: StepLSTM,
        window_sizes: list[int] | None = None,
        device: str = "cpu",
    ):
        self.model = model
        self.window_sizes = window_sizes or [16, 32, 48]
        self.device = device
        self.model.eval()

        # Feature buffer (most recent features at the front)
        self._feature_buffer: list[np.ndarray] = []
        self._max_window = max(self.window_sizes)

    def reset(self):
        """Clear the feature buffer."""
        self._feature_buffer.clear()

    def add_feature(self, feature: np.ndarray):
        """Add a new frame feature to the buffer."""
        self._feature_buffer.append(feature)
        # Keep only the largest window worth of features
        if len(self._feature_buffer) > self._max_window:
            self._feature_buffer = self._feature_buffer[-self._max_window:]

    def predict(self) -> tuple[int, np.ndarray]:
        """Predict current step using multi-scale voting.

        Returns:
            (predicted_class, probability_distribution)
        """
        if len(self._feature_buffer) < self.window_sizes[0]:
            # Not enough data yet
            num_classes = self.model.fc[-1].out_features
            return -1, np.zeros(num_classes, dtype=np.float32)

        probs_list = []

        with torch.no_grad():
            for ws in self.window_sizes:
                if len(self._feature_buffer) < ws:
                    continue

                # Take the last `ws` features
                window = self._feature_buffer[-ws:]
                x = torch.tensor(
                    np.array(window), dtype=torch.float32
                ).unsqueeze(0).to(self.device)  # (1, ws, feature_size)

                logits = self.model(x)
                probs = torch.softmax(logits, dim=-1).squeeze(0).cpu().numpy()
                probs_list.append(probs)

        if not probs_list:
            num_classes = self.model.fc[-1].out_features
            return -1, np.zeros(num_classes, dtype=np.float32)

        # Average probabilities across scales
        avg_probs = np.mean(probs_list, axis=0)
        predicted = int(np.argmax(avg_probs))

        return predicted, avg_probs

    def buffer_size(self) -> int:
        """Return current buffer size."""
        return len(self._feature_buffer)


def create_model(input_size: int, hidden_size: int, num_classes: int) -> StepLSTM:
    """Create a new LSTM model."""
    return StepLSTM(input_size=input_size, hidden_size=hidden_size, num_classes=num_classes)


def save_model(model: StepLSTM, path: str | Path, metadata: dict | None = None):
    """Save model weights and metadata."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state_dict": model.state_dict(),
        "input_size": model.lstm.input_size,
        "hidden_size": model.lstm.hidden_size,
        "num_layers": model.lstm.num_layers,
        "num_classes": model.fc[-1].out_features,
    }
    if metadata:
        payload["metadata"] = metadata
    torch.save(payload, path)
    logger.info(f"Model saved to {path}")


def load_model(path: str | Path) -> StepLSTM:
    """Load model from file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Model not found: {path}")

    payload = torch.load(path, map_location="cpu", weights_only=False)
    model = StepLSTM(
        input_size=payload["input_size"],
        hidden_size=payload["hidden_size"],
        num_classes=payload["num_classes"],
        num_layers=payload["num_layers"],
    )
    model.load_state_dict(payload["state_dict"])
    logger.info(f"Model loaded from {path}")
    return model
