from PIL import Image, ImageDraw, ImageFont
import io
import imageio
import numpy as np
import tempfile
import os

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def draw_text_with_spacing(draw, text, position, font, fill, spacing_percent):
    x, y = position
    spacing_px = font.size * spacing_percent
    
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        char_width = draw.textlength(char, font=font)
        x += char_width + spacing_px

def fit_text_to_width(draw, text, font, max_width, spacing_percent):
    current_width = 0
    spacing_px = font.size * spacing_percent
    
    for char in text:
        current_width += draw.textlength(char, font=font) + spacing_px
        
    if current_width <= max_width:
        return text

    temp_text = text
    while current_width > max_width and len(temp_text) > 0:
        temp_text = temp_text[:-1]
        check_text = temp_text + "..."
        current_width = 0
        for char in check_text:
            current_width += draw.textlength(char, font=font) + spacing_px
            
    return temp_text + "..."

# --- 1. АКТИВНЫЙ ПОЛЬЗОВАТЕЛЬ ---
def create_active_user_image(avatar_bytes, msg_count, user_name):
    try:
        img = Image.open("bg_active.png").convert("RGBA")
    except FileNotFoundError:
        img = Image.new("RGBA", (2000, 2000), (235, 87, 87))

    if avatar_bytes:
        try:
            avatar_size = (910, 910)
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize(avatar_size, Image.Resampling.LANCZOS)
            
            mask = Image.new("L", avatar_size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0) + avatar_size, fill=255)
            
            img.paste(avatar, (555, 471), mask)
        except Exception:
            pass

    try:
        overlay = Image.open("ramka.png").convert("RGBA")
        img.paste(overlay, (0, 0), overlay)
    except FileNotFoundError:
        pass

    draw = ImageDraw.Draw(img)

    try:
        font_big = ImageFont.truetype("stolzl_bold.otf", 250)
    except IOError:
        font_big = ImageFont.load_default()
    
    draw.text((159, 720), str(msg_count), font=font_big, fill=(255, 255, 255))

    try:
        font_desc = ImageFont.truetype("stolzl_bold.otf", 54)
    except IOError:
        font_desc = ImageFont.load_default()

    full_text = f"{user_name} написал больше всего сообщений в чате ({msg_count}) !"
    
    x_pos = 159
    max_width = 640
    line_height = 54
    text_color = "#52546F"
    target_bottom_y = 1649 

    words = full_text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        w = draw.textlength(test_line, font=font_desc)
        if w <= max_width:
            current_line.append(word)
        else:
            lines.append(' '.join(current_line))
            current_line = [word]
    lines.append(' '.join(current_line))

    total_height = len(lines) * line_height
    start_y = target_bottom_y - total_height
    current_y = start_y
    for line in lines:
        draw_text_with_spacing(draw, line, (x_pos, current_y), font_desc, text_color, -0.04)
        current_y += line_height

    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# --- 2. ТОП СЛОВ ---
def create_top_words_image(top_words):
    try:
        img = Image.open("bg_words.png").convert("RGBA")
    except FileNotFoundError:
        img = Image.new("RGBA", (2000, 2000), (235, 87, 87))

    draw = ImageDraw.Draw(img)
    
    font_sizes = [150, 145, 135]
    start_x = 174
    current_y = 714
    gap = 30
    max_width_list = 1600
    
    try:
        font_desc = ImageFont.truetype("stolzl_bold.otf", 48)
    except IOError:
        font_desc = ImageFont.load_default()

    for i in range(3):
        if i >= len(top_words): break
        word, count = top_words[i]
        try:
            font = ImageFont.truetype("stolzl_bold.otf", font_sizes[i])
        except IOError:
            font = ImageFont.load_default()
            
        text_line = f"{i+1}. {word}"
        final_text = fit_text_to_width(draw, text_line, font, max_width_list, -0.04)
        draw_text_with_spacing(draw, final_text, (start_x, current_y), font, (255, 255, 255), -0.04)
        current_y += font_sizes[i] + gap

    if top_words:
        best_word, best_count = top_words[0]
        text_content = f"Было использовано ровно {best_count} слов “{best_word}” !"
        
        x_pos = 159
        max_width_desc = 640
        line_height = 48
        desc_color = "#3D5258"
        target_bottom_y = 1649

        words = text_content.split()
        lines = []
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            w = draw.textlength(test_line, font=font_desc)
            if w <= max_width_desc:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
        lines.append(' '.join(current_line))

        total_height = len(lines) * line_height
        start_y = target_bottom_y - total_height
        current_y = start_y
        for line in lines:
            draw_text_with_spacing(draw, line, (x_pos, current_y), font_desc, desc_color, -0.04)
            current_y += line_height

    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# --- 3. ТОП СТИКЕР (ФИНАЛЬНЫЙ) ---
def create_top_sticker_image(sticker_bytes, count):
    # 1. Фон
    try:
        img = Image.open("bg_sticker.png").convert("RGBA")
    except FileNotFoundError:
        img = Image.new("RGBA", (2000, 2000), (240, 240, 240))

    # --- НАСТРОЙКИ ---
    max_sticker_size = 800  # Максимальный размер (как на шаблоне)
    box_x = 218             # Координата X
    box_y = 551             # Координата Y

    # 2. Наложение стикера
    if sticker_bytes:
        try:
            sticker = Image.open(io.BytesIO(sticker_bytes)).convert("RGBA")
            
            old_w, old_h = sticker.size
            ratio = min(max_sticker_size / old_w, max_sticker_size / old_h)
            new_w = int(old_w * ratio)
            new_h = int(old_h * ratio)
            
            sticker = sticker.resize((new_w, new_h), Image.Resampling.LANCZOS)

            final_w, final_h = sticker.size
            paste_x = box_x + (max_sticker_size - final_w) // 2
            paste_y = box_y + (max_sticker_size - final_h) // 2
            
            img.paste(sticker, (paste_x, paste_y), sticker)
        except Exception as e:
            print(f"Ошибка стикера: {e}")

    # 3. Текст
    draw = ImageDraw.Draw(img)
    try:
        font_desc = ImageFont.truetype("stolzl_bold.otf", 54)
    except IOError:
        font_desc = ImageFont.load_default()

    full_text = f"Было использовано ровно {count} этих стикеров"
    
    x_pos = 159
    max_width = 640 
    line_height = 55
    text_color = "#A35F5F"
    target_bottom_y = 1649 

    words = full_text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        w = draw.textlength(test_line, font=font_desc)
        if w <= max_width:
            current_line.append(word)
        else:
            lines.append(' '.join(current_line))
            current_line = [word]
    lines.append(' '.join(current_line))

    total_height = len(lines) * line_height
    start_y = target_bottom_y - total_height
    current_y = start_y
    for line in lines:
        draw_text_with_spacing(draw, line, (x_pos, current_y), font_desc, text_color, -0.04)
        current_y += line_height

    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

def create_top_sticker_gif(video_bytes, count):
    # Оптимизированная версия для Render (ffmpeg без pyav)
    temp_video = None
    reader = None
    try:
        bg_img_path = "bg_sticker.png"
        if not os.path.exists(bg_img_path):
            base_bg = Image.new("RGBA", (2000, 2000), (240, 240, 240))
        else:
            base_bg = Image.open(bg_img_path).convert("RGBA")
        
        max_sticker_size = 800
        box_x = 218
        box_y = 551
        
        # Записываем видео
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix='.webm')
        temp_video.write(video_bytes)
        temp_video.close()
        
        frames = []
        
        # --- ГЛАВНОЕ ИЗМЕНЕНИЕ ---
        # Используем imageio.get_reader (v2 API), который использует imageio-ffmpeg
        # Это надежнее всего и не требует установки 'av'
        try:
            reader = imageio.get_reader(temp_video.name, 'ffmpeg')
        except Exception as e:
            print(f"Ошибка открытия видео: {e}")
            return None
        
        try:
            font_desc = ImageFont.truetype("stolzl_bold.otf", 54)
        except IOError:
            font_desc = ImageFont.load_default()

        full_text = f"Было использовано ровно {count} этих стикеров"
        x_pos = 159
        max_width = 640
        line_height = 55
        text_color = "#A35F5F"
        target_bottom_y = 1649
        
        tmp_draw = ImageDraw.Draw(base_bg)
        words = full_text.split()
        lines = []
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            w = tmp_draw.textlength(test_line, font=font_desc)
            if w <= max_width:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
        lines.append(' '.join(current_line))
        total_height = len(lines) * line_height
        start_y = target_bottom_y - total_height

        # Читаем кадры через итератор reader
        for i, frame in enumerate(reader):
            # Пропуск кадров (экономия ресурсов)
            if i % 2 != 0:
                continue
                
            frame_img = Image.fromarray(frame).convert("RGBA")
            
            old_w, old_h = frame_img.size
            ratio = min(max_sticker_size / old_w, max_sticker_size / old_h)
            new_w = int(old_w * ratio)
            new_h = int(old_h * ratio)
            frame_img = frame_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            final_w, final_h = frame_img.size
            paste_x = box_x + (max_sticker_size - final_w) // 2
            paste_y = box_y + (max_sticker_size - final_h) // 2
            
            frame_with_bg = base_bg.copy()
            frame_with_bg.paste(frame_img, (paste_x, paste_y), frame_img)
            
            draw = ImageDraw.Draw(frame_with_bg)
            current_y = start_y
            for line in lines:
                draw_text_with_spacing(draw, line, (x_pos, current_y), font_desc, text_color, -0.04)
                current_y += line_height
            
            # Уменьшаем размер кадра для оптимизации размера файла
            frame_with_bg.thumbnail((512, 512), Image.Resampling.LANCZOS)
            
            frames.append(np.array(frame_with_bg.convert("RGB")))
            
            # Ограничитель, чтобы не зависнуть
            if len(frames) > 50:
                break
        
        reader.close()

        if os.path.exists(temp_video.name):
            os.unlink(temp_video.name)

        if not frames:
            return None

        # Зацикливаем кадры, если стикер слишком короткий
        # Минимальная длина: 5 секунд при 10 fps = 50 кадров
        min_frames = 50
        if len(frames) < min_frames:
            original_frames = frames.copy()
            while len(frames) < min_frames:
                frames.extend(original_frames)
            # Обрезаем до нужной длины
            frames = frames[:min_frames]

        # Сохраняем как MP4 используя временный файл (ffmpeg не может писать в BytesIO)
        temp_output = None
        try:
            temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            temp_output.close()
            
            writer = imageio.get_writer(temp_output.name, format='ffmpeg', codec='libx264', fps=10, pixelformat='yuv420p')
            for frame in frames:
                writer.append_data(frame)
            writer.close()
            
            # Читаем готовый MP4 в BytesIO
            with open(temp_output.name, 'rb') as f:
                output_io = io.BytesIO(f.read())
            
            # Удаляем временный файл
            if os.path.exists(temp_output.name):
                os.unlink(temp_output.name)
            
            output_io.seek(0)
            return output_io
        except Exception as e:
            print(f"Ошибка создания MP4: {e}")
            # Очищаем временный файл при ошибке
            if temp_output and os.path.exists(temp_output.name):
                try:
                    os.unlink(temp_output.name)
                except:
                    pass
            # Fallback на GIF если MP4 не получился
            output_io = io.BytesIO()
            imageio.mimsave(output_io, frames, format='GIF', loop=0, duration=0.1)
            output_io.seek(0)
            return output_io

    except Exception as e:
        print(f"Ошибка обработки видео-стикера: {e}")
        if temp_video and os.path.exists(temp_video.name):
            try: os.unlink(temp_video.name)
            except: pass
        if reader:
            reader.close()
        return None