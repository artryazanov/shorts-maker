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

load_dotenv()

short_length = 36


def detect_video_scenes(video_path, threshold=27.0):
    # Open our video, create a scene manager, and add a detector.
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(
        ContentDetector(threshold=threshold))
    scene_manager.detect_scenes(video, show_progress=True)
    return scene_manager.get_scene_list()


def render_video(clip, video_file_name):
    # Resize the video
    w, h = clip.size
    current_ratio = w / h
    target_ratio = 1920 / 1920

    if current_ratio > target_ratio:
        # The video is wider than the desired aspect ratio, crop the width
        new_width = int(h * target_ratio)
        x_center = w / 2
        y_center = h / 2
        clip = crop_vid.crop(clip, width=new_width, height=h, x_center=x_center, y_center=y_center)
    else:
        # The video is taller than the desired aspect ratio, crop the height
        new_height = int(w / target_ratio)
        x_center = w / 2
        y_center = h / 2
        clip = crop_vid.crop(clip, width=w, height=new_height, x_center=x_center, y_center=y_center)

    # Write the final video
    print('Render final video...')
    clip.write_videofile("generated/" + os.path.basename(video_file_name), codec='libx264', audio_codec='aac')


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
        if (scene[1].get_seconds() - scene[0].get_seconds()) > short_length:
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
            max_start_point = math.floor((scene[1].get_seconds() - short_length))

            start_point = random.randint(min_start_point, max_start_point)
            final_clip = video_clip.subclip(start_point, start_point + short_length)

            split_tup = os.path.splitext(video_file)
            render_file_name = split_tup[0] + '_scene_' + str(i) + split_tup[1]
            render_video(final_clip, render_file_name)
    else:
        if video_clip.duration < 60:
            min_start_point = 0
            max_finish_point = 0
        else:
            min_start_point = 12
            max_finish_point = 12

        max_start_point = math.floor(video_clip.duration - short_length - max_finish_point)

        start_point = random.randint(min_start_point, max_start_point)
        final_clip = video_clip.subclip(start_point, start_point + short_length)

        render_video(final_clip, video_file)
