import os
import subprocess
from PIL import Image, ImageDraw, ImageFont
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

def create_shorts_background_frame(title, category, frame_path):
    img = Image.new('RGB', (config.SHORTS_WIDTH, config.SHORTS_HEIGHT), color=(15, 17, 23))
    draw = ImageDraw.Draw(img)
    
    cat_info = config.CATEGORIES.get(category, {'color': '#3b82f6', 'name': '재활운동'})
    font_path = config.FONT_PATH
    badge_font = ImageFont.truetype(font_path, 34) if font_path else ImageFont.load_default()
    title_font = ImageFont.truetype(font_path, 52) if font_path else ImageFont.load_default()
    logo_font = ImageFont.truetype(font_path, 40) if font_path else ImageFont.load_default()
    
    draw.text((100, 180), config.BRAND_NAME, fill=(255, 255, 255), font=logo_font)
    draw.rounded_rectangle([(100, 260), (340, 325)], radius=14, fill=cat_info['color'])
    draw.text((120, 274), cat_info['name'], fill=(255, 255, 255), font=badge_font)
    
    draw.rounded_rectangle([(80, 420), (config.SHORTS_WIDTH - 80, 800)], radius=24, fill=(28, 32, 42))
    draw.text((120, 480), title, fill=(255, 255, 255), font=title_font, spacing=20)
    
    draw.text((120, config.SHORTS_HEIGHT - 260), "팔로우하고 더 많은 재활 정보를 받아보세요!", fill=(156, 163, 175), font=badge_font)
    
    img.save(frame_path, quality=95)
    return frame_path

def render_shorts_video(shorts_data, audio_path, srt_path, output_video_path):
    os.makedirs(os.path.dirname(output_video_path), exist_ok=True)
    temp_frame = os.path.join(os.path.dirname(output_video_path), "temp_bg.png")
    create_shorts_background_frame(shorts_data['title'], shorts_data.get('category', 'spine'), temp_frame)
    
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", temp_frame,
        "-i", audio_path,
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest", output_video_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(temp_frame):
        os.remove(temp_frame)
        
    print(f"[Shorts Renderer] Generated video: {output_video_path}")
    return output_video_path
