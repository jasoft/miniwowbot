import sys
import logging
from pathlib import Path

# --- Setup for local usage (not needed if installed via pip) ---
sys.path.append(str(Path(__file__).parent / "libraries" / "colored_context_logger" / "src"))
# -------------------------------------------------------------

from colored_context_logger import setup_logger, GlobalLogContext, attach_file_handler

def main():
    # 1. Setup the logger
    logger = setup_logger(name="FileLogDemo", level="DEBUG")
    
    # 2. Set some context
    # This helps when inspecting logs later to know who did what
    GlobalLogContext.update({
        "app_version": "1.0.0",
        "environment": "staging"
    })

    print("--- 1. Auto-named File Logging ---")
    # Scenario: You want a log file per session or run.
    # By setting 'session' in the context, the logger can auto-generate a meaningful filename.
    GlobalLogContext.update({"session": "batch_job_123"})
    
    # Attach a handler. If filename is omitted, it uses 'session' from context + timestamp.
    auto_log_path = attach_file_handler(
        logger_name="FileLogDemo", 
        log_dir="logs_example"
    )
    print(f"Auto-generated log file: {auto_log_path}")
    
    logger.info("This message goes to the auto-named file.")
    logger.debug("Debug info for the batch job.")

    print("\n--- 2. Specific Named File Logging ---")
    # Scenario: You want a dedicated error log that persists or has a fixed name.
    error_log_path = attach_file_handler(
        logger_name="FileLogDemo",
        log_dir="logs_example",
        filename="errors.log",
        level="ERROR" # Only capture ERROR and CRITICAL
    )
    print(f"Error log file: {error_log_path}")

    logger.info("This is info - visible in auto-log but NOT in error-log.")
    logger.error("This is an error - visible in BOTH files.")

    print("\n--- Verification ---")
    if Path(auto_log_path).exists():
        print(f"✓ {auto_log_path} created.")
    
    if Path(error_log_path).exists():
        print(f"✓ {error_log_path} created.")

if __name__ == "__main__":
    main()
