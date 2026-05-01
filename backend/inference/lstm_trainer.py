"""LSTM model training with simulated data."""

import logging
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from backend.inference.lstm_classifier import StepLSTM, save_model
from backend.inference.mock_data import generate_training_data
from backend.inference.feature_fusion import FUSED_FEATURE_SIZE

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "models"


class LstmTrainer:
    """Trains an LSTM step classifier on synthetic data."""

    def __init__(
        self,
        num_classes: int = 5,
        input_size: int = FUSED_FEATURE_SIZE,
        hidden_size: int = 128,
        num_layers: int = 2,
        learning_rate: float = 1e-3,
        epochs: int = 30,
        batch_size: int = 32,
    ):
        self.num_classes = num_classes
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lr = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size

        self.model: StepLSTM | None = None
        self.training_history: list[dict] = []
        self._is_training = False

    @property
    def is_training(self) -> bool:
        return self._is_training

    def train(self, progress_callback=None) -> dict:
        """Train the model on synthetic data.

        Args:
            progress_callback: Optional callback(epoch, total_epochs, loss, accuracy)

        Returns:
            Training summary dict.
        """
        self._is_training = True
        start_time = time.time()

        try:
            # Generate training data
            logger.info(f"Generating synthetic data: {self.num_classes} classes, 100 samples each")
            X, y, lengths = generate_training_data(
                num_classes=self.num_classes,
                samples_per_class=100,
            )

            # Create data loader
            dataset = TensorDataset(
                torch.tensor(X, dtype=torch.float32),
                torch.tensor(y, dtype=torch.long),
            )
            loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

            # Create model
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = StepLSTM(
                input_size=self.input_size,
                hidden_size=self.hidden_size,
                num_classes=self.num_classes,
                num_layers=self.num_layers,
            ).to(device)

            optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)
            criterion = nn.CrossEntropyLoss()

            self.training_history = []

            logger.info(f"Training LSTM on {device} for {self.epochs} epochs")
            for epoch in range(self.epochs):
                self.model.train()
                total_loss = 0.0
                correct = 0
                total = 0

                for batch_X, batch_y in loader:
                    batch_X = batch_X.to(device)
                    batch_y = batch_y.to(device)

                    optimizer.zero_grad()
                    outputs = self.model(batch_X)
                    loss = criterion(outputs, batch_y)
                    loss.backward()
                    optimizer.step()

                    total_loss += loss.item() * batch_X.size(0)
                    _, predicted = torch.max(outputs, 1)
                    correct += (predicted == batch_y).sum().item()
                    total += batch_y.size(0)

                avg_loss = total_loss / total
                accuracy = correct / total

                record = {
                    "epoch": epoch + 1,
                    "loss": round(avg_loss, 4),
                    "accuracy": round(accuracy, 4),
                }
                self.training_history.append(record)

                if progress_callback:
                    progress_callback(epoch + 1, self.epochs, avg_loss, accuracy)

                if (epoch + 1) % 10 == 0:
                    logger.info(f"Epoch {epoch + 1}/{self.epochs}: loss={avg_loss:.4f}, acc={accuracy:.4f}")

            # Save model
            model_path = MODEL_DIR / "lstm_step_classifier.pt"
            save_model(self.model, model_path, metadata={
                "num_classes": self.num_classes,
                "window_sizes": [16, 32, 48],
            })

            elapsed = time.time() - start_time
            summary = {
                "status": "completed",
                "epochs": self.epochs,
                "final_loss": self.training_history[-1]["loss"],
                "final_accuracy": self.training_history[-1]["accuracy"],
                "model_path": str(model_path),
                "elapsed_seconds": round(elapsed, 1),
                "history": self.training_history,
            }
            logger.info(f"Training completed in {elapsed:.1f}s, accuracy={summary['final_accuracy']}")
            return summary

        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {"status": "failed", "error": str(e)}
        finally:
            self._is_training = False

    def get_status(self) -> dict:
        """Return current training status."""
        return {
            "is_training": self._is_training,
            "num_classes": self.num_classes,
            "epochs": self.epochs,
            "history": self.training_history,
        }
