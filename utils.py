from PIL import Image

def is_reserved_area(x, y, size, version):
    # 1. Finder Patterns și Format Information (cele 3 colțuri mari + marginile lor)
    # Acoperă zonele de 9x9 din colțuri pentru a proteja și biții de format/versiune
    if (x < 9 and y < 9) or (x < 9 and y >= size - 8) or (x >= size - 8 and y < 9):
        return True

    # 2. Timing Patterns (Liniile punctate de la rândul/coloana 6)
    if x == 6 or y == 6:
        return True

    # 3. Alignment Patterns (Pătrățelele de sincronizare 5x5)
    # Stocăm doar coordonatele centrale pentru fiecare versiune
    alignment_coords = {
        2: [(18, 18)],
        3: [(22, 22)],
        4: [(26, 26)],
        5: [(30, 30)],
        6: [(34, 34)]
    }

    if version in alignment_coords:
        for cx, cy in alignment_coords[version]:
            if abs(x - cx) <= 2 and abs(y - cy) <= 2:
                return True

    return False

def detect_qr_scale(image_path):
    with Image.open(image_path) as img:
        # Convertim imaginea la Grayscale ('L') pentru a avea valori de la 0 la 255
        # Indiferent dacă sursa a fost RGB, RGBA sau CMYK.
        img = img.convert("L")
        width, height = img.size

        scale = 0
        for i in range(min(width, height)):
            pixel_value = img.getpixel((i, i))

            # Folosim un prag de 128 (mijlocul intervalului 0-255)
            # pentru a fi siguri că detectăm albul chiar și în imagini cu zgomot.
            if pixel_value > 128:
                break
            scale += 1

    return scale

def scale_down(img_path, scale_factor):
    img = Image.open(img_path)
    new_size = (img.width // scale_factor, img.height // scale_factor)
    return img.resize(new_size, Image.NEAREST)

def get_pixel_binary_value(img, x, y):
    pixel = img.getpixel((x, y))

    if isinstance(pixel, int):
        return 1 if pixel == 0 else 0
    else:
        return 1 if sum(pixel[:3]) / 3 < 128 else 0

def apply_format_bits(matrix, format_bits):
    """
    Plasează cei 15 biți de format în zonele rezervate de lângă Finder Patterns.
    Dacă 'format_bits' este un șir de 15 zerouri, funcția acționează ca un 'eraser' (demascare).
    """
    size = len(matrix)

    # Partea 1: Lângă Finder-ul Top-Left (Sub și la dreapta)
    for i in range(6):
        matrix[8][i] = int(format_bits[i])
    matrix[8][7] = int(format_bits[6])

    # Partea 2: Lângă Finder-ul Top-Right
    for i in range(8):
        matrix[8][size - 8 + i] = int(format_bits[7 + i])

    # Partea 3: Lângă Finder-ul Bottom-Left
    for i in range(7):
        matrix[size - 1 - i][8] = int(format_bits[i])

    # Partea 4: Lângă Finder-ul Top-Left (Vertical)
    for i in range(2):
        matrix[8 - i][8] = int(format_bits[7 + i])
    for i in range(6):
        matrix[5 - i][8] = int(format_bits[9 + i])

    return matrix

