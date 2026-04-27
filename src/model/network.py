"""
src/model/network.py
Architecture du réseau de neurones pour la prédiction de matchs de football.
Classification 3 classes : Home (H), Draw (D), Away (A).
"""

import torch
import torch.nn as nn


class ResidualBlock(nn.Module):
    """Bloc résiduel : skip-connection + couche dense."""

    def __init__(self, dim: int, dropout: float) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.block(x)


class MatchPredictor(nn.Module):
    """
    MLP avec blocs résiduels pour données tabulaires.
    Architecture : Projection → N blocs résiduels → Tête de classification.
    """

    def __init__(
        self,
        input_dim: int = 16,
        hidden_dim: int = 64,
        num_residual_blocks: int = 2,
        dropout: float = 0.3,
        num_classes: int = 3,
    ) -> None:
        super().__init__()

        self.input_proj = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )

        self.residual_blocks = nn.Sequential(
            *[ResidualBlock(hidden_dim, dropout) for _ in range(num_residual_blocks)]
        )

        self.head = nn.Linear(hidden_dim, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_proj(x)
        x = self.residual_blocks(x)
        return self.head(x)

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Retourne les probabilités softmax pour chaque classe."""
        self.eval()
        with torch.no_grad():
            logits = self.forward(x)
            return torch.softmax(logits, dim=-1)


# ============================================================
# Config par défaut du modèle
# ============================================================
DEFAULT_MODEL_CONFIG: dict = {
    "input_dim": 40,
    "hidden_dim": 128,
    "num_residual_blocks": 3,
    "dropout": 0.3,
    "num_classes": 3,
}

# Mapping des indices vers les résultats
CLASS_LABELS: dict[int, str] = {0: "H", 1: "D", 2: "A"}
LABEL_TO_INDEX: dict[str, int] = {"H": 0, "D": 1, "A": 2}
