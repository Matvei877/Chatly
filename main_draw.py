from PIL import Image, ImageDraw, ImageFont
import io

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
    box_x = 218             # Координата X, которую ты просил
    box_y = 551             # Координата Y, которую ты просил

    # 2. Наложение стикера
    if sticker_bytes:
        try:
            sticker = Image.open(io.BytesIO(sticker_bytes)).convert("RGBA")
            
            # --- ЛОГИКА УВЕЛИЧЕНИЯ (ПРИНУДИТЕЛЬНАЯ) ---
            old_w, old_h = sticker.size
            
            # Считаем коэффициент, чтобы вписать картинку в 800x800,
            # но при этом УВЕЛИЧИТЬ её, если она меньше.
            ratio = min(max_sticker_size / old_w, max_sticker_size / old_h)
            
            new_w = int(old_w * ratio)
            new_h = int(old_h * ratio)
            
            # Используем resize, чтобы растянуть маленькие стикеры
            sticker = sticker.resize((new_w, new_h), Image.Resampling.LANCZOS)
            # --------------------------

            # Центрируем стикер в зоне 800x800
            # Если стикер квадратный, он встанет ровно в 218, 551
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
    max_width = 640  # Граница текста (чтобы не был строкой)
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