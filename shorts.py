"""Utility for automatically generating short video clips.

This module processes gameplay videos and creates resized clips
that fit common short-video aspect ratios. Scene detection is used
to select interesting parts of the video and background blurring is
applied when required.

The script was refactored to improve readability and maintainability
while retaining the original behaviour.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np
from dotenv import load_dotenv
from moviepy.editor import CompositeVideoClip, VideoFileClip
import moviepy.video.fx.crop as crop_vid
from scipy.ndimage import gaussian_filter
from scenedetect import SceneManager, open_video
from scenedetect.detectors import ContentDetector


# Load environment variables from a .env file if present.
load_dotenv()

# Configure basic logging. The calling application may override this
# configuration if a different format is required.
logging.basicConfig(level=logging.INFO, format="%(message)s")


@dataclass(frozen=True)
class ProcessingConfig:
    """Configuration values used throughout the processing pipeline."""

    target_ratio_w: int = 1
    target_ratio_h: int = 1
    scene_limit: int = 6
    x_center: float = 0.5
    y_center: float = 0.5
    max_error_depth: int = 3
    min_short_length: int = 15
    max_short_length: int = 179
    max_combined_scene_length: int = 300

    @property
    def middle_short_length(self) -> float:
        """Return the mid point between min and max short lengths."""

        return (self.min_short_length + self.max_short_length) / 2


def detect_video_scenes(video_path: Path, threshold: float = 27.0) -> Sequence[Tuple] | List:
    """Detect scenes in the provided video file.

    Parameters
    ----------
    video_path: Path
        Path to the video file.
    threshold: float, optional
        Threshold value for the ``ContentDetector``.

    Returns
    -------
    Sequence[Tuple]
        List of ``(start, end)`` timecodes for each detected scene.
    """

    video = open_video(str(video_path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))
    scene_manager.detect_scenes(video, show_progress=True)
    return scene_manager.get_scene_list()


def blur(image: np.ndarray) -> np.ndarray:
    """Return a blurred version of ``image``."""

    return gaussian_filter(image.astype(float), sigma=8)


def crop_clip(
    clip: VideoFileClip,
    ratio_w: int,
    ratio_h: int,
    x_center: float,
    y_center: float,
):
    """Crop ``clip`` to the desired aspect ratio.

    The centre of the crop is determined by ``x_center`` and ``y_center``,
    which are expressed as fractions of the clip's width and height.
    """

    width, height = clip.size
    current_ratio = width / height
    target_ratio = ratio_w / ratio_h

    if current_ratio > target_ratio:
        new_width = round(height * ratio_w / ratio_h)
        return crop_vid.crop(
            clip,
            width=new_width,
            height=height,
            x_center=width * x_center,
            y_center=height * y_center,
        )

    new_height = round(width / ratio_w * ratio_h)
    return crop_vid.crop(
        clip,
        width=width,
        height=new_height,
        x_center=width * x_center,
        y_center=height * y_center,
    )


def render_video(
    clip: VideoFileClip,
    video_file_name: Path,
    output_dir: Path,
    depth: int = 0,
    max_error_depth: int = 3,
) -> None:
    """Render ``clip`` to ``output_dir`` with error retries."""

    try:
        clip.write_videofile(
            str(output_dir / video_file_name.name),
            codec="libx264",
            audio_codec="aac",
            fps=min(getattr(clip, "fps", 60), 60),
        )
    except Exception:  # pragma: no cover - logging only
        if depth < max_error_depth:
            logging.exception("Rendering failed, retrying...")
            render_video(clip, video_file_name, output_dir, depth + 1, max_error_depth)
        else:
            logging.exception("Rendering failed after multiple attempts.")


def select_background_resolution(width: int) -> Tuple[int, int]:
    """Choose an output resolution based on the clip width."""

    if width < 840:
        return 720, 1280
    if width < 1020:
        return 900, 1600
    if width < 1320:
        return 1080, 1920
    if width < 1680:
        return 1440, 2560
    if width < 2040:
        return 1800, 3200
    return 2160, 3840


def get_final_clip(
    clip: VideoFileClip,
    start_point: float,
    final_clip_length: float,
    config: ProcessingConfig,
) -> VideoFileClip:
    """Prepare a clip ready for rendering."""

    result_clip = clip.subclip(start_point, start_point + final_clip_length)

    width, height = result_clip.size
    target_ratio = config.target_ratio_w / config.target_ratio_h
    if width / height > target_ratio:
        result_clip = crop_clip(
            result_clip,
            config.target_ratio_w,
            config.target_ratio_h,
            config.x_center,
            config.y_center,
        )

    width, height = result_clip.size
    bg_w, bg_h = select_background_resolution(width)
    result_clip = result_clip.resize(width=bg_w)

    if width >= height:
        background_clip = clip.subclip(start_point, start_point + final_clip_length)
        background_clip = crop_clip(background_clip, 1, 1, config.x_center, config.y_center)
        background_clip = background_clip.resize(width=720, height=720)
        background_clip = background_clip.fl_image(blur)
        background_clip = background_clip.resize(width=bg_w, height=bg_w)
        result_clip = CompositeVideoClip([background_clip, result_clip.set_position("center")])
    elif width / 9 < height / 16:
        background_clip = clip.subclip(start_point, start_point + final_clip_length)
        background_clip = crop_clip(background_clip, 9, 16, config.x_center, config.y_center)
        background_clip = background_clip.resize(width=720, height=1280)
        background_clip = background_clip.fl_image(blur)
        background_clip = background_clip.resize(width=bg_w, height=bg_h)
        result_clip = CompositeVideoClip([background_clip, result_clip.set_position("center")])

    return result_clip


def combine_scenes(scene_list: Sequence[Tuple], config: ProcessingConfig) -> List[List]:
    """Combine short scenes into larger ones to meet minimum duration."""

    combined_small_scene = None
    combined_large_scene = None
    combined_scene_list: List[List] = []

    for i, scene in enumerate(scene_list):
        duration = scene[1].get_seconds() - scene[0].get_seconds()

        if (
            len(scene_list) > 1
            and (i == 0 or i == len(scene_list) - 1)
            and duration < config.min_short_length
        ):
            continue

        if duration < config.min_short_length:
            if combined_small_scene is None:
                combined_small_scene = [scene[0], scene[1]]
            else:
                combined_small_scene[1] = scene[1]
                combined_duration = (
                    combined_small_scene[1].get_seconds()
                    - combined_small_scene[0].get_seconds()
                )
                if combined_duration >= config.max_combined_scene_length:
                    combined_scene_list.append(combined_small_scene)
                    combined_small_scene = None

            if combined_large_scene is not None:
                combined_duration = (
                    combined_large_scene[1].get_seconds()
                    - combined_large_scene[0].get_seconds()
                )
                if combined_duration >= config.middle_short_length:
                    combined_scene_list.append(combined_large_scene)
                combined_large_scene = None
        else:
            if combined_large_scene is None:
                combined_large_scene = [scene[0], scene[1]]
            else:
                combined_large_scene[1] = scene[1]

            if combined_small_scene is not None:
                combined_duration = (
                    combined_small_scene[1].get_seconds()
                    - combined_small_scene[0].get_seconds()
                )
                if combined_duration >= config.middle_short_length:
                    combined_scene_list.append(combined_small_scene)
                combined_small_scene = None

    if combined_small_scene is not None:
        combined_duration = (
            combined_small_scene[1].get_seconds()
            - combined_small_scene[0].get_seconds()
        )
        if combined_duration >= config.middle_short_length:
            combined_scene_list.append(combined_small_scene)

    if combined_large_scene is not None:
        combined_duration = (
            combined_large_scene[1].get_seconds()
            - combined_large_scene[0].get_seconds()
        )
        if combined_duration >= config.middle_short_length:
            combined_scene_list.append(combined_large_scene)

    return combined_scene_list


def process_video(video_file: Path, config: ProcessingConfig, output_dir: Path) -> None:
    """Process a single video file and generate short clips."""

    logging.info("\nProcess: %s", video_file.name)
    logging.info("Detecting scenes...")
    scene_list = detect_video_scenes(video_file)

    combined_scene_list = combine_scenes(scene_list, config)
    logging.info("Combined scenes list:")
    for i, scene in enumerate(combined_scene_list, start=1):
        logging.info(
            "    Combined Scene %2d: Duration %d Start %s / Frame %d, End %s / Frame %d",
            i,
            scene[1].get_seconds() - scene[0].get_seconds(),
            scene[0].get_timecode(),
            scene[0].get_frames(),
            scene[1].get_timecode(),
            scene[1].get_frames(),
        )

    sorted_combined_scene_list = sorted(
        combined_scene_list,
        key=lambda s: s[1].get_seconds() - s[0].get_seconds(),
        reverse=True,
    )

    video_clip = VideoFileClip(str(video_file))
    truncated_list = sorted_combined_scene_list[: config.scene_limit]

    logging.info("Truncated sorted combined scenes list:")
    for i, scene in enumerate(truncated_list, start=1):
        logging.info(
            "    Scene %2d: Duration %d Start %s / Frame %d, End %s / Frame %d",
            i,
            scene[1].get_seconds() - scene[0].get_seconds(),
            scene[0].get_timecode(),
            scene[0].get_frames(),
            scene[1].get_timecode(),
            scene[1].get_frames(),
        )

    if truncated_list:
        for i, scene in enumerate(truncated_list):
            duration = math.floor(scene[1].get_seconds() - scene[0].get_seconds())
            short_length = random.randint(
                config.min_short_length, min(config.max_short_length, duration)
            )

            min_start = math.floor(scene[0].get_seconds())
            max_start = math.floor(scene[1].get_seconds() - short_length)

            final_clip = get_final_clip(
                video_clip,
                random.randint(min_start, max_start),
                short_length,
                config,
            )

            render_file_name = f"{video_file.stem} scene-{i}{video_file.suffix}"
            render_video(
                final_clip,
                Path(render_file_name),
                output_dir,
                max_error_depth=config.max_error_depth,
            )
    else:
        short_length = random.randint(
            config.min_short_length, config.max_short_length
        )

        if video_clip.duration < config.max_short_length:
            adapted_short_length = min(math.floor(video_clip.duration), short_length)
        else:
            adapted_short_length = short_length

        min_start_point = min(10, math.floor(video_clip.duration) - adapted_short_length)
        max_start_point = math.floor(video_clip.duration - adapted_short_length)
        final_clip = get_final_clip(
            video_clip,
            random.randint(min_start_point, max_start_point),
            adapted_short_length,
            config,
        )
        render_video(
            final_clip,
            video_file,
            output_dir,
            max_error_depth=config.max_error_depth,
        )


def main() -> None:
    """Entry point for command-line execution."""

    config = ProcessingConfig()
    output_dir = Path("generated")
    output_dir.mkdir(exist_ok=True)

    gameplay_dir = Path("gameplay")
    for video_file in gameplay_dir.iterdir():
        if video_file.is_file():
            process_video(video_file, config, output_dir)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()

