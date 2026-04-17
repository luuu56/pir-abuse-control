from pathlib import Path
import yaml


CONFIG_PATH = Path("configs/common/base.yaml")


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
