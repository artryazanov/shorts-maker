# Import everything
from dotenv import load_dotenv
import random
import os
import openai
from gtts import gTTS
from moviepy.editor import *
import moviepy.video.fx.crop as crop_vid
from scenedetect import open_video, SceneManager, split_video_ffmpeg
from scenedetect.detectors import ContentDetector, ThresholdDetector, AdaptiveDetector
import math
import skimage
from scipy.ndimage import gaussian_filter
import copy

load_dotenv()

SHORT_LENGTH = random.randint(25, 55)


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


def crop_clip(clip, target_ratio):
    # Resize the video
    w, h = clip.size
    current_ratio = w / h

    if current_ratio > target_ratio:
        # The video is wider than the desired aspect ratio, crop the width
        new_width = int(h * target_ratio)
        x_center = w / 2
        y_center = h / 2
        cropped_clip = crop_vid.crop(clip, width=new_width, height=h, x_center=x_center, y_center=y_center)
    else:
        # The video is taller than the desired aspect ratio, crop the height
        new_height = int(w / target_ratio)
        x_center = w / 2
        y_center = h / 2
        cropped_clip = crop_vid.crop(clip, width=w, height=new_height, x_center=x_center, y_center=y_center)

    return cropped_clip


def render_video(clip, video_file_name):
    clip.write_videofile("generated/" + os.path.basename(video_file_name), codec='libx264', audio_codec='aac')


def get_final_clip(clip, start_point, final_clip_length):
    result_clip = clip.subclip(start_point, start_point + final_clip_length)

    w, h = result_clip.size
    if w / h > 4 / 3:
        result_clip = crop_clip(result_clip, 4 / 3)

    w, h = result_clip.size
    if w > 2160:
        result_clip = result_clip.resize(width=2160)

    w, h = result_clip.size
    if w / h > 3 / 4:
        background_clip = crop_clip(result_clip, 9 / 16)
        w, h = background_clip.size
        process_blur_width = min(1080, w)
        background_clip = background_clip.resize(width=process_blur_width)
        background_clip = background_clip.fl_image(blur)
        w, h = result_clip.size
        background_clip = background_clip.resize(width=w)
        result_clip = CompositeVideoClip([background_clip, result_clip.set_position("center")])

    return result_clip


dir_list = os.listdir('gameplay')
for video_file in dir_list:
    print('\r\nProcess: ' + video_file)

    # Create the directory
    if not os.path.exists('generated'):
        os.mkdir('generated')

    print('Detecting scenes...')
    scene_list = detect_video_scenes(os.path.abspath('gameplay') + '/' + video_file, 64.0)
    good_scene_list = []
    for i, scene in enumerate(scene_list):
        print('    Scene %2d: Start %s / Frame %d, End %s / Frame %d' % (
            i + 1,
            scene[0].get_timecode(), scene[0].get_frames(),
            scene[1].get_timecode(), scene[1].get_frames(),))
        if (scene[1].get_seconds() - scene[0].get_seconds()) > SHORT_LENGTH:
            good_scene_list.append(scene)

    print('Good scenes list:')
    for i, scene in enumerate(good_scene_list):
        print('    Good Scene %2d: Start %s / Frame %d, End %s / Frame %d' % (
            i + 1,
            scene[0].get_timecode(), scene[0].get_frames(),
            scene[1].get_timecode(), scene[1].get_frames(),))

    video_clip = VideoFileClip(os.path.abspath('gameplay') + '/' + video_file)

    if len(good_scene_list) > 0:
        for i, scene in enumerate(good_scene_list):
            min_start_point = math.floor(scene[0].get_seconds())
            max_start_point = math.floor((scene[1].get_seconds() - SHORT_LENGTH))

            final_clip = get_final_clip(video_clip, random.randint(min_start_point, max_start_point), SHORT_LENGTH)

            split_tup = os.path.splitext(video_file)
            render_file_name = split_tup[0] + ' scene-' + str(i) + split_tup[1]
            render_video(final_clip, render_file_name)
    else:
        if video_clip.duration < 60:
            short_length = min(math.floor(video_clip.duration), SHORT_LENGTH)
        else:
            short_length = SHORT_LENGTH

        min_start_point = min(10, math.floor(video_clip.duration) - short_length)
        max_start_point = math.floor(video_clip.duration - short_length)
        final_clip = get_final_clip(video_clip, random.randint(min_start_point, max_start_point), short_length)
        render_video(final_clip, video_file)
