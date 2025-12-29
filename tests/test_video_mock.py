
import os
import cv2
import pytest
from ocr_helper import OCRHelper
import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class VideoMockEmulator:
    def __init__(self, video_path):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
        self.frame_count = 0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        logger.info(f"Initialized VideoMockEmulator with {video_path}")
        logger.info(f"Total frames: {self.total_frames}, FPS: {self.fps}")

    def snapshot(self, filename=None, *args, **kwargs):
        """
        Mock snapshot function that reads the next frame from the video.
        """
        ret, frame = self.cap.read()
        if not ret:
            logger.info("End of video reached, restarting...")
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if not ret:
                raise EOFError("Could not read video frame even after restart")
        
        if filename:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            cv2.imwrite(filename, frame)
            logger.debug(f"Saved video frame {self.frame_count} to {filename}")
        
        self.frame_count += 1
        return frame

    def close(self):
        self.cap.release()

@pytest.fixture(scope="module")
def video_mock():
    video_path = r"C:\Users\11885\Videos\BlueStacks-Pie64\Recording-2025-12-26-005653.mp4"
    if not os.path.exists(video_path):
        pytest.skip(f"Video file not found: {video_path}")
    
    emulator = VideoMockEmulator(video_path)
    yield emulator
    emulator.close()

def test_video_ocr_flow(video_mock):
    """
    Test OCR on video frames.
    """
    # Initialize OCRHelper with the mock snapshot function
    ocr_helper = OCRHelper(output_dir="output/test_video", snapshot_func=video_mock.snapshot)
    
    # Process a few frames
    num_frames_to_test = 5
    found_any_text = False
    
    for i in range(num_frames_to_test):
        logger.info(f"Processing frame {i+1}/{num_frames_to_test}...")
        
        # Capture and get all texts
        results = ocr_helper.capture_and_get_all_texts(use_cache=False)
        
        logger.info(f"Frame {i+1} found {len(results)} text elements")
        for res in results[:5]: # Print first 5 results
            logger.info(f"  - {res.get('text')} at {res.get('center')}")
            
        if len(results) > 0:
            found_any_text = True
            
        # Simulate some time passing if needed, though for the mock it just grabs the next frame
        # In a real scenario, you might want to skip frames to simulate real-time
        
    assert found_any_text, "OCR should detect text in at least one frame of the video"

if __name__ == "__main__":
    # Allow running directly
    pytest.main([__file__, "-v", "-s", "--log-cli-level=INFO"])
