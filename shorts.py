# Import everything
from dotenv import load_dotenv
import random
import os
import openai
from gtts import gTTS
from moviepy.editor import *
import moviepy.video.fx.crop as crop_vid

load_dotenv()

short_length = 35

# Ask for video info
video_file_path = input("\nEnter video file path >  ")
option = input('Do you want AI to generate content? (yes/no) >  ')

if option == 'yes':
    # Generate content using OpenAI API
    theme = input("\nEnter the theme of the video >  ")

    ### MAKE .env FILE AND SAVE YOUR API KEY ###
    openai.api_key = os.environ["OPENAI_API"]
    response = openai.Completion.create(
        engine="gpt-3.5-turbo-instruct",
        prompt=f"Generate content on - \"{theme}\"",
        temperature=0.7,
        max_tokens=768,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )
    print(response.choices[0].text)

    yes_no = input('\nIs this fine? (yes/no) >  ')
    if yes_no == 'yes':
        content = response.choices[0].text
    else:
        content = input('\nEnter >  ')
else:
    content = input('\nEnter the content of the video >  ')

# Create the directory
if not os.path.exists('generated'):
    os.mkdir('generated')

# Generate speech for the video
speech = gTTS(text=content, lang='en', tld='ca', slow=False)
speech.save("generated/speech.mp3")

audio_clip = AudioFileClip("generated/speech.mp3")

if audio_clip.duration + 1.3 > short_length:
    print('\nSpeech too long!\n' + str(audio_clip.duration) + ' seconds\n' + str(audio_clip.duration + 1.3) + ' total')
    print('It will be cut to ' + str(short_length - 1.3) + ' seconds\n')
    audio_clip = audio_clip.subclip(0, short_length - 1.3)
    # exit()

print('\n')

### VIDEO EDITING ###

gp = random.choice(["1", "2"])
video_clip = VideoFileClip(video_file_path)
max_start_point = int(video_clip.duration - short_length - 1.3)
start_point = random.randint(5, max_start_point)

video_clip = video_clip.subclip(start_point, start_point + audio_clip.duration + 1.3)
video_clip = video_clip.volumex(0.25)
final_audio = CompositeAudioClip([video_clip.audio, audio_clip])

final_clip = video_clip.set_audio(final_audio)

# Resize the video to 9:16 ratio
w, h = final_clip.size
target_ratio = 1080 / 1920
current_ratio = w / h

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
final_clip.write_videofile("generated/" + os.path.basename(video_file_path) + ".mp4", codec='libx264', audio_codec='aac',
                           temp_audiofile='temp-audio.m4a', remove_temp=True)
