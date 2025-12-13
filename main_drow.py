from PIL import Image, ImageDraw, ImageFont
import os

# Исходные данные
mes_bol = 'Матвей (8 сообщ.)'
word = '"чиназес" (3 раз)'
longpost = 'да я люблю сосать член В Екатеринбурге пенсионерка пыталась'
hype = 'Матвей (+1 на "лан")'


def create_single_image(text, title, filename, bg_image_path=None):
    """Создает отдельное изображение для одной категории"""
    try:
        # Определяем размеры изображения
        width, height = 600, 200

        # Создаем изображение (белый фон или загружаем фон)
        if bg_image_path and os.path.exists(bg_image_path):
            image = Image.open(bg_image_path)
            # Обрезаем или изменяем размер фона под нужный размер
            image = image.resize((width, height))
            print(f"Используем фоновое изображение: {bg_image_path}")
        else:
            # Создаем изображение с белым фоном
            image = Image.new('RGB', (width, height), color='white')
            print("Создано изображение с белым фоном")

        # Создаем объект для рисования
        drawer = ImageDraw.Draw(image)

        # Загружаем шрифты
        try:
            # Путь к системному шрифту Arial (Windows)
            font_path = r"C:\Windows\Fonts\arial.ttf"
            title_font = ImageFont.truetype(font_path, 24)
            text_font = ImageFont.truetype(font_path, 18)
        except:
            print("Используем стандартный шрифт (arial.ttf не найден)")
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()

        # Добавляем заголовок (название категории)
        title_position = (20, 20)
        drawer.text(title_position, title, font=title_font, fill='black')

        # Добавляем основной текст
        # Разбиваем длинный текст на строки, если он не помещается
        max_chars_per_line = 50
        lines = []
        current_line = ""

        for char in text:
            if len(current_line) < max_chars_per_line:
                current_line += char
            else:
                lines.append(current_line)
                current_line = char

        if current_line:
            lines.append(current_line)

        # Рисуем каждую строку текста
        text_start_y = 70
        line_height = 30

        for i, line in enumerate(lines):
            y_position = text_start_y + (i * line_height)
            drawer.text((20, y_position), line, font=text_font, fill='black')

        # Сохраняем результат
        image.save(filename)
        print(f"Изображение сохранено как: {filename}")

        # Показываем изображение
        image.show()

        return True

    except Exception as e:
        print(f"Произошла ошибка при создании изображения {filename}: {e}")
        return False


def create_all_images():
    """Создает все изображения для каждой категории"""

    # Проверяем существование фонового изображения (если нужно)
    bg_image_path = r"E:\Chatly\image.jpg"
    if not os.path.exists(bg_image_path):
        print(f"Фоновое изображение '{bg_image_path}' не найдено. Будут использоваться белые фоны.")
        bg_image_path = None

    # Создаем изображения для каждой категории
    images_info = [
        {
            'title': 'Самое длинное сообщение:',
            'text': mes_bol,
            'filename': 'longest_message.jpg'
        },
        {
            'title': 'Самое популярное слово:',
            'text': word,
            'filename': 'popular_word.jpg'
        },
        {
            'title': 'Самый длинный пост:',
            'text': longpost,
            'filename': 'longest_post.jpg'
        },
        {
            'title': 'Хайп:',
            'text': hype,
            'filename': 'hype.jpg'
        }
    ]

    # Создаем каждое изображение
    created_count = 0
    for img_info in images_info:
        success = create_single_image(
            text=img_info['text'],
            title=img_info['title'],
            filename=img_info['filename'],
            bg_image_path=bg_image_path
        )
        if success:
            created_count += 1

    print(f"\nИтог: создано {created_count} из {len(images_info)} изображений")

    # Показать список созданных файлов
    print("\nСозданные файлы:")
    for file in os.listdir('.'):
        if file.endswith(('.jpg', '.jpeg', '.png')):
            print(f"  - {file}")


if __name__ == "__main__":
    create_all_images()