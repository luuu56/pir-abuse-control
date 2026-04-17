from common.config import load_config
from common.logging_utils import setup_logger


def main():
    config = load_config()
    logger = setup_logger("pir_server", config)
    app_name = config.get("app_name", "unknown-app")
    logger.info("pir_server service bootstrap ok | app=%s", app_name)


if __name__ == "__main__":
    main()