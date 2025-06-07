# Import everything
from dotenv import load_dotenv
import random
from moviepy.editor import *
import moviepy.video.fx.crop as crop_vid
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector
import math
from scipy.ndimage import gaussian_filter

load_dotenv()

my_target_ratio_w = 1  # default 4
my_target_ratio_h = 1  # default 3
my_scene_limit = 6  # default 12
my_x_center = 0.5  # default 0.5
my_y_center = 0.5  # default 0.5
my_max_error_depth = 3


def detect_video_scenes(video_path, threshold=27.0):
    # Open our video, create a scene manager, and add a detector.
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(
        ContentDetector(threshold=threshold))
    scene_manager.detect_scenes(video, show_progress=True)
    return scene_manager.get_scene_list()


def blur(image):
    """ Returns a blurred (radius=8 pixels) version of the image """
    return gaussian_filter(image.astype(float), sigma=8)


def crop_clip(clip, target_ratio_w, target_ratio_h):
    # Resize the video
    w, h = clip.size
    current_ratio = w / h
    target_ratio = target_ratio_w / target_ratio_h

    if current_ratio > target_ratio:
        # The video is wider than the desired aspect ratio, crop the width
        new_width = round(h * target_ratio_w / target_ratio_h)
        x_center = w * my_x_center
        y_center = h * my_y_center
        cropped_clip = crop_vid.crop(clip, width=new_width, height=h, x_center=x_center, y_center=y_center)
    else:
        # The video is taller than the desired aspect ratio, crop the height
        new_height = round(w / target_ratio_w * target_ratio_h)
        x_center = w * my_x_center
        y_center = h * my_y_center
        cropped_clip = crop_vid.crop(clip, width=w, height=new_height, x_center=x_center, y_center=y_center)

    return cropped_clip


def render_video(clip, video_file_name, depth = 0):
    try:
        clip.write_videofile("generated/" + os.path.basename(video_file_name), codec='libx264', audio_codec='aac', fps=min(clip.fps, 60))
    except:
        if depth < my_max_error_depth:
            print('\r\n\r\nAN EXCEPTION OCCURRED! TRY render_video AGAIN!\r\n\r\n')
            render_video(clip, video_file_name, depth + 1)
        else:
            print('\r\n\r\nAN EXCEPTION OCCURRED! TOO MUCH ERRORS! GO AHEAD!\r\n\r\n')


def get_final_clip(clip, start_point, final_clip_length):
    result_clip = clip.subclip(start_point, start_point + final_clip_length)

    w, h = result_clip.size
    if w / h > my_target_ratio_w / my_target_ratio_h:
        result_clip = crop_clip(result_clip, my_target_ratio_w, my_target_ratio_h)

    w, h = result_clip.size
    if w < 840:
        bg_w = 720
        bg_h = 1280
    elif w < 1020:
        bg_w = 900
        bg_h = 1600
    elif w < 1320:
        bg_w = 1080
        bg_h = 1920
    elif w < 1680:
        bg_w = 1440
        bg_h = 2560
    elif w < 2040:
        bg_w = 1800
        bg_h = 3200
    else:
        bg_w = 2160
        bg_h = 3840

    result_clip = result_clip.resize(width=bg_w)

    if w >= h:
        background_clip = clip.subclip(start_point, start_point + final_clip_length)
        background_clip = crop_clip(background_clip, 1, 1)
        background_clip = background_clip.resize(width=720, height=720)
        background_clip = background_clip.fl_image(blur)
        background_clip = background_clip.resize(width=bg_w, height=bg_w)
        result_clip = CompositeVideoClip([background_clip, result_clip.set_position("center")])
    elif w / 9 < h / 16:
        background_clip = clip.subclip(start_point, start_point + final_clip_length)
        background_clip = crop_clip(background_clip, 9, 16)
        background_clip = background_clip.resize(width=720, height=1280)
        background_clip = background_clip.fl_image(blur)
        background_clip = background_clip.resize(width=bg_w, height=bg_h)
        result_clip = CompositeVideoClip([background_clip, result_clip.set_position("center")])

    return result_clip


min_short_length = 15
max_short_length = 179
max_combined_scene_length = 300
middle_short_length = (min_short_length + max_short_length) / 2

# Create the directory
if not os.path.exists('generated'):
    os.mkdir('generated')

dir_list = os.listdir('gameplay')
for video_file in dir_list:

    print('\r\nProcess: ' + video_file)

    print('Detecting scenes...')
    scene_list = detect_video_scenes(os.path.abspath('gameplay') + '/' + video_file)

    combined_small_scene = None
    combined_large_scene = None
    combined_scene_list = []
    for i, scene in enumerate(scene_list):
        duration = scene[1].get_seconds() - scene[0].get_seconds()

        print('    Scene %2d: Duration %d Start %s / Frame %d, End %s / Frame %d' % (
            i + 1,
            duration,
            scene[0].get_timecode(), scene[0].get_frames(),
            scene[1].get_timecode(), scene[1].get_frames(),))

        if (len(scene_list) > 1) and ((i == 0) or (i == (len(scene_list) - 1))) and (duration < min_short_length):
            continue

        if duration < min_short_length:
            if combined_small_scene is None:
                combined_small_scene = [scene[0], scene[1]]
            else:
                combined_small_scene[1] = scene[1]
                combined_duration = combined_small_scene[1].get_seconds() - combined_small_scene[0].get_seconds()
                if combined_duration >= max_combined_scene_length:
                    combined_scene_list.append(combined_small_scene)
                    combined_small_scene = None

            if combined_large_scene is not None:
                combined_duration = combined_large_scene[1].get_seconds() - combined_large_scene[0].get_seconds()
                if combined_duration >= middle_short_length:
                    combined_scene_list.append(combined_large_scene)
                combined_large_scene = None

        else:
            if combined_large_scene is None:
                combined_large_scene = [scene[0], scene[1]]
            else:
                combined_large_scene[1] = scene[1]

            if combined_small_scene is not None:
                combined_duration = combined_small_scene[1].get_seconds() - combined_small_scene[0].get_seconds()
                if combined_duration >= middle_short_length:
                    combined_scene_list.append(combined_small_scene)
                combined_small_scene = None

    if combined_small_scene is not None:
        combined_duration = combined_small_scene[1].get_seconds() - combined_small_scene[0].get_seconds()
        if combined_duration >= middle_short_length:
            combined_scene_list.append(combined_small_scene)

    if combined_large_scene is not None:
        combined_duration = combined_large_scene[1].get_seconds() - combined_large_scene[0].get_seconds()
        if combined_duration >= middle_short_length:
            combined_scene_list.append(combined_large_scene)

    print('Combined scenes list:')
    for i, scene in enumerate(combined_scene_list):
        print('    Combined Scene %2d: Duration %d Start %s / Frame %d, End %s / Frame %d' % (
            i + 1,
            scene[1].get_seconds() - scene[0].get_seconds(),
            scene[0].get_timecode(), scene[0].get_frames(),
            scene[1].get_timecode(), scene[1].get_frames(),))

    sorted_combined_scene_list = sorted(combined_scene_list, key=lambda s: s[1].get_seconds() - s[0].get_seconds(), reverse=True)

    video_clip = VideoFileClip(os.path.abspath('gameplay') + '/' + video_file)

    scene_limit = my_scene_limit

    truncated_sorted_combined_scene_list = sorted_combined_scene_list[:scene_limit]

    print('Truncated sorted combined scenes list:')
    for i, scene in enumerate(truncated_sorted_combined_scene_list):
        print('    Scene %2d: Duration %d Start %s / Frame %d, End %s / Frame %d' % (
            i + 1,
            scene[1].get_seconds() - scene[0].get_seconds(),
            scene[0].get_timecode(), scene[0].get_frames(),
            scene[1].get_timecode(), scene[1].get_frames(),))


    if len(truncated_sorted_combined_scene_list) > 0:
        for i, scene in enumerate(truncated_sorted_combined_scene_list):
            duration = math.floor(scene[1].get_seconds() - scene[0].get_seconds())
            short_length = random.randint(min_short_length, min(max_short_length, duration))

            min_start_point = math.floor(scene[0].get_seconds())
            max_start_point = math.floor((scene[1].get_seconds() - short_length))

            final_clip = get_final_clip(video_clip, random.randint(min_start_point, max_start_point), short_length)

            split_tup = os.path.splitext(video_file)
            render_file_name = split_tup[0] + ' scene-' + str(i) + split_tup[1]
            render_video(final_clip, render_file_name)
    else:
        short_length = random.randint(min_short_length, max_short_length)

        if video_clip.duration < max_short_length:
            adapted_short_length = min(math.floor(video_clip.duration), short_length)
        else:
            adapted_short_length = short_length

        min_start_point = min(10, math.floor(video_clip.duration) - adapted_short_length)
        max_start_point = math.floor(video_clip.duration - adapted_short_length)
        final_clip = get_final_clip(video_clip, random.randint(min_start_point, max_start_point), adapted_short_length)
        render_video(final_clip, video_file)
