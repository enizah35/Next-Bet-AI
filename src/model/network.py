"""
src/model/network.py
Architecture du réseau de neurones pour la prédiction de matchs de football.
Classification 3 classes : Home (H), Draw (D), Away (A).
"""

import torch
import torch.nn as nn


class MatchPredictor(nn.Module):
    """
    Réseau de neurones fully-connected (MLP) allégé pour données tabulaires.
    Très efficace pour la prédiction avec un nombre restreint de features (17).
    """

    def __init__(
        self,
        input_dim: int = 17,
        hidden_dim: int = 64,
        num_residual_blocks: int = 2,  # gardé pour compatibilité de signature mais non utilisé ou défini comme profondeur
        dropout: float = 0.1,
        num_classes: int = 3,
    ) -> None:
        super().__init__()

        self.net = nn.Sequential(
            nn.Linear(input_dim, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass complet.
        """
        return self.net(x)

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
    "input_dim": 17,
    "hidden_dim": 64,
    "num_residual_blocks": 2,
    "dropout": 0.1,
    "num_classes": 3,
}

# Mapping des indices vers les résultats
CLASS_LABELS: dict[int, str] = {0: "H", 1: "D", 2: "A"}
LABEL_TO_INDEX: dict[str, int] = {"H": 0, "D": 1, "A": 2}
