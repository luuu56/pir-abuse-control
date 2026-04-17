import logging
from pathlib import Path
import yaml


CONFIG_PATH = Path("configs/common/base.yaml")


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logger(config: dict) -> logging.Logger:
    log_dir = Path(config.get("log_dir", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level_name = config.get("log_level", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logger = logging.getLogger("verifier")
    logger.setLevel(log_level)

    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
        )

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        file_handler = logging.FileHandler(log_dir / "verifier.log", encoding="utf-8")
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger


def main():
    config = load_config()
    logger = setup_logger(config)
    app_name = config.get("app_name", "unknown-app")
    logger.info("verifier service bootstrap ok | app=%s", app_name)


if __name__ == "__main__":
    main()