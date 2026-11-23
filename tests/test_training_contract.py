from pathlib import Path

import pytest
import yaml

from src.train import generate_campaigns, selected_features


def test_post_outcome_feature_is_rejected(tmp_path: Path) -> None:
    contract = {
        "selected": ["measured_outcome"],
        "features": {"measured_outcome": {"known_at_prediction_time": False}},
    }
    path = tmp_path / "features.yaml"
    path.write_text(yaml.safe_dump(contract), encoding="utf-8")
    with pytest.raises(ValueError, match="Forbidden post-outcome"):
        selected_features(path)


def test_campaign_generator_is_reproducible_and_covers_both_phases() -> None:
    first = generate_campaigns(42, campaigns=5)
    second = generate_campaigns(42, campaigns=5)
    assert first.equals(second)
    lengths = first.groupby("campaign_id").size()
    assert lengths.between(60, 120).all()
    assert (first["item_position"] < 50).any()
    assert (first["item_position"] >= 50).any()
