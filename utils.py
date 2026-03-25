from PIL import Image
from config import ALIGNMENT_PATTERN_COORDS

def is_reserved_area(x: int, y: int, size: int, version: int) -> bool:
    """
    Verifică apartenența coordonatelor (x, y) în zonele rezervate a codului QR
    (Finder Patterns, Timing Lines, Alignment Patterns sau Format Info).
    """
    # 1. Finder Patterns și Format Information (colțurile mari)
    if (x < 9 and y < 9) or (x < 9 and y >= size - 8) or (x >= size - 8 and y < 9):
        return True

    # 2. Timing Patterns (Liniile punctate)
    if x == 6 or y == 6:
        return True

    # 3. Alignment Patterns (preluăm coordonatele din config)
    if version in ALIGNMENT_PATTERN_COORDS:
        for cx, cy in ALIGNMENT_PATTERN_COORDS[version]:
            if abs(x - cx) <= 2 and abs(y - cy) <= 2:
                return True

    return False

def detect_qr_scale(image_path: str) -> int:
    """
    Detectează automat dimensiunea unui modul QR (scale) numărând pixelii
    negri de pe diagonală până la prima zonă albă a Finder Pattern-ului.
    """
    with Image.open(image_path) as img:
        img = img.convert("L")
        width, height = img.size

        scale = 0
        for i in range(min(width, height)):
            if img.getpixel((i, i)) > 128:
                break
            scale += 1

    return scale


def scale_down(img_path: str, scale_factor: int) -> Image.Image:
    """Redimensionează imaginea la o scară mai mică folosind interpolare NEAREST."""
    with Image.open(img_path) as img:
        new_size = (img.width // scale_factor, img.height // scale_factor)
        return img.resize(new_size, Image.NEAREST)


def get_pixel_binary_value(img: Image.Image, x: int, y: int) -> int:
    """Determină valoarea binară (1=Negru, 0=Alb) a unui pixel."""
    pixel = img.getpixel((x, y))

    if isinstance(pixel, int):
        # Folosim < 128 pentru a fi rezistenți la imagini ușor încețoșate
        return 1 if pixel < 128 else 0
    else:
        return 1 if sum(pixel[:3]) / 3 < 128 else 0


def apply_format_bits(matrix: list, format_bits: str) -> list:
    """
    Plasează cei 15 biți de format în zonele rezervate de lângă Finder Patterns.
    Dacă 'format_bits' este un șir de 15 zerouri, funcția acționează ca un 'eraser'.
    """
    size = len(matrix)

    for i in range(6): matrix[8][i] = int(format_bits[i])
    matrix[8][7] = int(format_bits[6])

    for i in range(8): matrix[8][size - 8 + i] = int(format_bits[7 + i])
    for i in range(7): matrix[size - 1 - i][8] = int(format_bits[i])

    for i in range(2): matrix[8 - i][8] = int(format_bits[7 + i])
    for i in range(6): matrix[5 - i][8] = int(format_bits[9 + i])

    return matrix