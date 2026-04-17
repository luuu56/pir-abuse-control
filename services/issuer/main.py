from common.config import load_config
from common.logging_utils import setup_logger


def main():
    config = load_config()
    logger = setup_logger("issuer", config)
    app_name = config.get("app_name", "unknown-app")
    logger.info("issuer service bootstrap ok | app=%s", app_name)


if __name__ == "__main__":
    main()