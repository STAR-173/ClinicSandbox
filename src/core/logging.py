import sys
import structlog
import logging
from src.core.config import settings

def setup_logging():
    """
    Configures structlog to output JSON in Production and 
    colored strings in Development.
    """
    
    # Shared processors (add timestamp, log level, stack info)
    shared_processors = [
        structlog.contextvars.merge_contextvars, # Allows binding job_id globally
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
    ]

    if settings.ENVIRONMENT == "production":
        # PROD: Flat JSON for Datadog/ELK
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # DEV: Human readable
        processors = shared_processors + [
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ]

    # Configure Structlog
    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
    
    # Intercept standard library logging (e.g. Uvicorn logs)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    
    # Replace the root logger handler to use structlog
    # This ensures third-party libs (like SQLAlchemy) use our JSON format
    def handle_exception(exc_type, exc_value, exc_traceback):
        """
        Global exception handler to ensure crashes are logged as JSON
        """
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        root_logger = structlog.get_logger()
        root_logger.critical(
            "uncaught_exception",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = handle_exception