"""Tests for OCR and logger package availability."""

import os
import cv2
import numpy as np

# Standard imports (installed via uv add)
import vibe_ocr
from vibe_logger import setup_logger, GlobalLogContext, attach_file_handler
import vibe_logger

def test_ocr_and_logger():
    # 1. Setup Logger
    logger = setup_logger("test_ocr", level="DEBUG")
    GlobalLogContext.update({"session": "test_run_123"})
    
    # Verify installation source
    logger.info(f"vibe_ocr file: {vibe_ocr.__file__}")
    logger.info(f"vibe_logger file: {vibe_logger.__file__}")
    
    # Create logs directory if it doesn't exist
    if not os.path.exists("logs_test"):
        os.makedirs("logs_test")
        
    log_file = attach_file_handler("test_ocr", log_dir="logs_test", filename="test_output.log")
    
    logger.info("Starting test...")
    logger.info(f"Log file: {log_file}")

    # 2. Setup OCR Helper
    ocr_server = os.environ.get("OCR_SERVER_URL", "http://192.168.1.150:8081/ocr")
    os.environ["OCR_SERVER_URL"] = ocr_server
    
    logger.info(f"Using OCR Server: {ocr_server}")
    
    ocr = vibe_ocr.OCRHelper(output_dir="output_test")    
    # 3. Create a dummy image with text
    # Create a white image
    width, height = 600, 200
    image = np.ones((height, width, 3), dtype=np.uint8) * 255
    
    # Add text
    font = cv2.FONT_HERSHEY_SIMPLEX
    text = "HELLO WORLD 123"
    org = (50, 100)
    fontScale = 2
    color = (0, 0, 0) # Black
    thickness = 3
    
    cv2.putText(image, text, org, font, fontScale, color, thickness, cv2.LINE_AA)
    
    image_path = "test_image_generated.png"
    cv2.imwrite(image_path, image)
    logger.info(f"Created test image: {image_path}")

    try:
        # 4. Run OCR
        logger.info(f"Sending image {image_path} to OCR...")
        
        # Test finding "HELLO"
        result = ocr.find_text_in_image(image_path, "HELLO", use_cache=False)
        logger.info(f"OCR Result for 'HELLO': {result}")
        
        if result and result.get('found'):
            logger.info("✅ Successfully found 'HELLO'")
        else:
            logger.error("❌ Failed to find 'HELLO'")
            
        # Test finding "WORLD"
        result_world = ocr.find_text_in_image(image_path, "WORLD", use_cache=False)
        logger.info(f"OCR Result for 'WORLD': {result_world}")
        
        if result_world and result_world.get('found'):
            logger.info("✅ Successfully found 'WORLD'")
        else:
            logger.error("❌ Failed to find 'WORLD'")

    except Exception as e:
        logger.error(f"Failed during test execution: {e}")
        raise

    # Clean up
    if os.path.exists(image_path):
        os.remove(image_path)
    
    logger.info("Test finished.")

if __name__ == "__main__":
    test_ocr_and_logger()
