from PIL import Image, ImageDraw, ImageFont
import io

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def draw_text_with_spacing(draw, text, position, font, fill, spacing_percent):
    x, y = position
    # Вычисляем сдвиг в пикселях. Отрицательный процент сближает буквы.
    spacing_px = font.size * spacing_percent
    
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        char_width = draw.textlength(char, font=font)
        x += char_width + spacing_px

def fit_text_to_width(draw, text, font, max_width, spacing_percent):
    """
    Если текст не влезает в max_width, обрезаем его и добавляем '...'
    """
    current_width = 0
    spacing_px = font.size * spacing_percent
    
    # Сначала проверяем ширину полного текста
    for char in text:
        current_width += draw.textlength(char, font=font) + spacing_px
        
    if current_width <= max_width:
        return text

    # Если не влезает, обрезаем
    temp_text = text
    while current_width > max_width and len(temp_text) > 0:
        temp_text = temp_text[:-1]
        check_text = temp_text + "..."
        current_width = 0
        for char in check_text:
            current_width += draw.textlength(char, font=font) + spacing_px
            
    return temp_text + "..."

# --- 1. ФУНКЦИЯ ДЛЯ САМОГО АКТИВНОГО (СЛАЙД 1) ---
def create_active_user_image(avatar_bytes, msg_count, user_name):
    # 1. Фон
    try:
        img = Image.open("bg_active.png").convert("RGBA")
    except FileNotFoundError:
        img = Image.new("RGBA", (2000, 2000), (235, 87, 87))

    # 2. Аватарка
    if avatar_bytes:
        try:
            avatar_size = (900, 900)
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize(avatar_size, Image.Resampling.LANCZOS)
            
            mask = Image.new("L", avatar_size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0) + avatar_size, fill=255)
            
            img.paste(avatar, (555, 471), mask)
        except Exception as e:
            print(f"Ошибка аватара: {e}")

    # 3. Рамка
    try:
        overlay = Image.open("ramka.png").convert("RGBA")
        img.paste(overlay, (0, 0), overlay)
    except FileNotFoundError:
        pass

    draw = ImageDraw.Draw(img)

    # 4. Число сообщений
    try:
        font_big = ImageFont.truetype("stolzl_bold.otf", 165)
    except IOError:
        font_big = ImageFont.load_default()
    
    draw.text((159, 775), str(msg_count), font=font_big, fill=(255, 255, 255))

    # 5. Текст описания
    try:
        font_desc = ImageFont.truetype("stolzl_bold.otf", 48)
    except IOError:
        font_desc = ImageFont.load_default()

    full_text = f"{user_name} написал больше всего сообщений в чате ({msg_count}) !"
    
    x_pos = 159
    max_width = 640
    line_height = 48
    text_color = "#FFC881"
    
    # Bottom Align logic
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

# --- 2. ФУНКЦИЯ ДЛЯ ТОПА СЛОВ (СЛАЙД 2) ---
def create_top_words_image(top_words):
    try:
        img = Image.open("bg_words.png").convert("RGBA")
    except FileNotFoundError:
        img = Image.new("RGBA", (2000, 2000), (235, 87, 87))

    draw = ImageDraw.Draw(img)
    
    # --- БЛОК 1: СПИСОК ---
    font_sizes = [150, 145, 135]
    start_x = 174
    current_y = 714
    gap = 30
    max_width_list = 885
    
    spacing_percent = -0.04 
    text_color = (255, 255, 255)

    for i in range(3):
        if i >= len(top_words):
            break
            
        word, count = top_words[i]
        size = font_sizes[i]
        
        try:
            font = ImageFont.truetype("stolzl_bold.otf", size)
        except IOError:
            font = ImageFont.load_default()
            
        text_line = f"{i+1}. {word}"
        final_text = fit_text_to_width(draw, text_line, font, max_width_list, spacing_percent)
        
        draw_text_with_spacing(draw, final_text, (start_x, current_y), font, text_color, spacing_percent)
        
        current_y += size + gap

    # --- БЛОК 2: ОПИСАНИЕ СНИЗУ ---
    if top_words:
        best_word = top_words[0][0]
        best_count = top_words[0][1]

        try:
            font_desc = ImageFont.truetype("stolzl_bold.otf", 48)
        except IOError:
            font_desc = ImageFont.load_default()

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
            # Для описания оставил стандартный кернинг -0.04
            draw_text_with_spacing(draw, line, (x_pos, current_y), font_desc, desc_color, -0.04)
            current_y += line_height

    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio