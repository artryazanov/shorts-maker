# Import everything
from dotenv import load_dotenv
import random
import os
import openai
from gtts import gTTS
from moviepy.editor import *
import moviepy.video.fx.crop as crop_vid

load_dotenv()

min_start_point = 15
max_finish_point = 15
short_length = 36

dir_list = os.listdir('gameplay')
for video_file in dir_list:
    print('Process: ' + video_file)

    # Create the directory
    if not os.path.exists('generated'):
        os.mkdir('generated')

    video_clip = VideoFileClip(os.path.abspath('gameplay') + '/' + video_file)
    max_start_point = int(video_clip.duration - short_length - max_finish_point)
    start_point = random.randint(min_start_point, max_start_point)

    final_clip = video_clip.subclip(start_point, start_point + short_length)

    # Resize the video to 9:16 ratio
    w, h = final_clip.size
    current_ratio = w / h
    target_ratio = 1920 / 1920

    if current_ratio > target_ratio:
        # The video is wider than the desired aspect ratio, crop the width
        new_width = int(h * target_ratio)
        x_center = w / 2
        y_center = h / 2
        final_clip = crop_vid.crop(final_clip, width=new_width, height=h, x_center=x_center, y_center=y_center)
    else:
        # The video is taller than the desired aspect ratio, crop the height
        new_height = int(w / target_ratio)
        x_center = w / 2
        y_center = h / 2
        final_clip = crop_vid.crop(final_clip, width=w, height=new_height, x_center=x_center, y_center=y_center)

    # Write the final video
    final_clip.write_videofile("generated/" + os.path.basename(video_file), codec='libx264', audio_codec='aac',
                               temp_audiofile='temp-audio.m4a', remove_temp=True)
