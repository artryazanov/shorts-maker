import numpy as np
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from moviepy.editor import ColorClip

# Ensure the project root is on the import path.
import sys
import types
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Stub scenedetect to avoid heavy OpenCV dependency during import.
scenedetect_stub = types.ModuleType("scenedetect")
scenedetect_stub.SceneManager = object  # type: ignore
scenedetect_stub.open_video = lambda *_args, **_kwargs: None  # type: ignore

detectors_stub = types.ModuleType("scenedetect.detectors")
detectors_stub.ContentDetector = object  # type: ignore

sys.modules.setdefault("scenedetect", scenedetect_stub)
sys.modules.setdefault("scenedetect.detectors", detectors_stub)

import shorts
from shorts import (
    blur,
    combine_scenes,
    crop_clip,
    select_background_resolution,
    ProcessingConfig,
    render_video,
    scene_action_score,
    compute_audio_action_profile,
)


class MockTime:
    """Simple stand-in for scenedetect's time objects."""

    def __init__(self, seconds: float):
        self._seconds = seconds

    def get_seconds(self) -> float:
        return self._seconds

    # The functions below are unused in logic but required by combine_scenes
    def get_timecode(self) -> str:
        return str(self._seconds)

    def get_frames(self) -> int:
        return int(self._seconds * 30)


def make_scene(start: float, end: float):
    return (MockTime(start), MockTime(end))


def test_select_background_resolution():
    assert select_background_resolution(800) == (720, 1280)
    assert select_background_resolution(1500) == (1440, 2560)
    assert select_background_resolution(2100) == (2160, 3840)


def test_crop_clip_to_square():
    clip = ColorClip(size=(1920, 1080), color=(255, 0, 0), duration=1)
    cropped = crop_clip(clip, 1, 1, 0.5, 0.5)
    assert cropped.size == (1080, 1080)


def test_blur_changes_image():
    image = np.zeros((10, 10))
    image[5, 5] = 1.0
    blurred = blur(image)
    assert blurred.shape == image.shape
    assert blurred[5, 5] != image[5, 5]


def test_combine_scenes_merges_short_scenes():
    config = ProcessingConfig(min_short_length=5, max_short_length=10, max_combined_scene_length=15)
    scenes = [
        make_scene(0, 5),
        make_scene(5, 7),
        make_scene(7, 9),
        make_scene(9, 11),
        make_scene(11, 13),
        make_scene(13, 18),
    ]
    combined = combine_scenes(scenes, config)
    assert len(combined) == 1
    start, end = combined[0]
    assert start.get_seconds() == 5
    assert end.get_seconds() == 13


def test_render_video_retries(tmp_path):
    clip = MagicMock()
    clip.fps = 30
    clip.write_videofile.side_effect = [Exception("boom"), None]
    render_video(clip, Path("out.mp4"), tmp_path, max_error_depth=1)
    assert clip.write_videofile.call_count == 2




def test_render_video_raises_after_retries(tmp_path):
    clip = MagicMock()
    clip.fps = 60
    clip.write_videofile.side_effect = Exception("fail")

    with pytest.raises(Exception):
        render_video(clip, Path("out.mp4"), tmp_path, max_error_depth=0)



def test_scene_action_score_average():
    times = np.array([0, 1, 2, 3, 4, 5, 6], dtype=float)
    score = np.array([0, 10, 10, 10, 0, 0, 0], dtype=float)
    scene = make_scene(1.0, 4.0)
    avg = scene_action_score(scene, times, score)
    assert avg == pytest.approx(10.0, rel=1e-6)


def test_scene_action_score_empty_segment():
    times = np.array([0.0, 1.0], dtype=float)
    score = np.array([1.0, 1.0], dtype=float)
    scene = make_scene(2.0, 3.0)
    assert scene_action_score(scene, times, score) == 0.0


def test_scene_action_score_invalid_range():
    times = np.array([0.0], dtype=float)
    score = np.array([0.0], dtype=float)
    scene = make_scene(5.0, 5.0)
    assert scene_action_score(scene, times, score) == 0.0


def test_compute_audio_action_profile_stubbed(monkeypatch):
    class LibrosaStub:
        def load(self, path, sr=None, mono=True):
            return np.zeros(1000, dtype=float), 100

        class feature:
            @staticmethod
            def rms(y, frame_length=2048, hop_length=512):
                # Return shape (1, n_frames)
                return np.array([[1.0, 2.0, 3.0]], dtype=float)

        @staticmethod
        def stft(y, n_fft=2048, hop_length=512):
            # Shape (freq_bins, n_frames)
            return np.array(
                [
                    [1.0, 2.0, 3.0],
                    [1.0, 2.0, 3.0],
                ],
                dtype=float,
            )

        @staticmethod
        def frames_to_time(frames, sr=100, hop_length=512):
            return np.asarray(frames, dtype=float) * 0.01

    # Patch the librosa module used inside shorts
    monkeypatch.setattr(shorts, "librosa", LibrosaStub(), raising=False)

    times, score = compute_audio_action_profile(Path("dummy.mp4"))

    assert isinstance(times, np.ndarray)
    assert isinstance(score, np.ndarray)
    assert len(times) == len(score) == 3
    # Combined score should not be constant given our stub inputs
    assert score.std() > 0
