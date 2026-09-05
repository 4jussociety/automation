import os
import textwrap
from PIL import Image, ImageDraw, ImageFont
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

def render_cards(card_news_data, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    rendered_files = []
    
    font_path = config.FONT_PATH
    title_font = ImageFont.truetype(font_path, 54) if font_path else ImageFont.load_default()
    body_font = ImageFont.truetype(font_path, 36) if font_path else ImageFont.load_default()
    badge_font = ImageFont.truetype(font_path, 26) if font_path else ImageFont.load_default()
    footer_font = ImageFont.truetype(font_path, 28) if font_path else ImageFont.load_default()
    
    cat_info = config.CATEGORIES.get(card_news_data.get('category', 'spine'), {'color': '#3b82f6', 'name': '도수치료'})
    accent_color = cat_info['color']
    
    for slide in card_news_data['slides']:
        idx = slide['slide_number']
        img = Image.new('RGB', (config.CARD_WIDTH, config.CARD_HEIGHT), color=(18, 22, 28))
        draw = ImageDraw.Draw(img)
        
        badge_text = slide.get('badge', cat_info['name'])
        draw.rounded_rectangle([(80, 80), (80 + len(badge_text) * 26 + 40, 135)], radius=12, fill=accent_color)
        draw.text((100, 94), badge_text, fill=(255, 255, 255), font=badge_font)
        draw.text((config.CARD_WIDTH - 140, 94), f"{idx}/5", fill=(156, 163, 175), font=badge_font)
        
        headline = slide.get('headline', '')
        wrapped_headline = textwrap.fill(headline, width=16)
        draw.text((80, 240), wrapped_headline, fill=(255, 255, 255), font=title_font, spacing=20)
        
        draw.line([(80, 520), (config.CARD_WIDTH - 80, 520)], fill=(55, 65, 81), width=3)
        
        subtext = slide.get('subtext', '')
        wrapped_subtext = textwrap.fill(subtext, width=22)
        draw.text((80, 580), wrapped_subtext, fill=(209, 213, 219), font=body_font, spacing=20)
        
        draw.line([(80, config.CARD_HEIGHT - 150), (config.CARD_WIDTH - 80, config.CARD_HEIGHT - 150)], fill=(55, 65, 81), width=2)
        draw.text((80, config.CARD_HEIGHT - 110), config.BRAND_NAME, fill=(255, 255, 255), font=footer_font)
        draw.text((config.CARD_WIDTH - 260, config.CARD_HEIGHT - 110), config.BRAND_HANDLE, fill=(156, 163, 175), font=footer_font)
        
        file_path = os.path.join(output_dir, f"card_slide_{idx:02d}.png")
        img.save(file_path, quality=95)
        rendered_files.append(file_path)
        
    print(f"[Card Renderer] Rendered {len(rendered_files)} card slides to {output_dir}")
    return rendered_files
