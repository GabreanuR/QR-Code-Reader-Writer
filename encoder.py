import numpy as np
from PIL import Image
import reedsolo
import copy
import itertools

from config import BCH_POLYNOMIAL, FORMAT_XOR_MASK, ECC_LEVEL_HIGH, QR_CONFIG_HIGH, PADDING_BYTES, QR_BLOCK_CONFIG_HIGH, QR_MATRIX_SIZES, ALIGNMENT_PATTERN_COORDS
from utils import is_reserved_area, apply_format_bits

def generate_format_string(mask_id: int) -> str:
    """
    Generează șirul de 15 biți pentru Format Information.
    Include nivelul de eroare, ID-ul măștii și codul BCH(15, 5).
    """
    mask_bin = f"{mask_id:03b}"
    format_bits = ECC_LEVEL_HIGH + mask_bin

    # Facem spațiu (shift cu 10 biți) pentru a adăuga restul BCH
    info = int(format_bits, 2) << 10

    # Calculăm restul împărțirii polinomiale (folosind polinomul din config)
    for i in range(5):
        if info & (1 << (14 - i)):
            info ^= BCH_POLYNOMIAL << (4 - i)

    bch_bits = info & 0b1111111111

    # Combinăm biții și aplicăm XOR cu masca standard din config
    final_format = (int(format_bits, 2) << 10 | bch_bits) ^ FORMAT_XOR_MASK

    return f"{final_format:015b}"

def generate_ecc_for_block(data_bits: str, ecc_capacity: int) -> str:
    """
    Generează biții de Error Correction (ECC) pentru un bloc de date
    folosind algoritmul Reed-Solomon.
    """
    rs = reedsolo.RSCodec(ecc_capacity)

    data_bytes = bytearray(int(data_bits[i:i + 8], 2) for i in range(0, len(data_bits), 8))
    encoded_data = rs.encode(data_bytes)
    ecc_bytes = encoded_data[len(data_bytes):]

    return "".join(format(byte, '08b') for byte in ecc_bytes)

def apply_mask(qr_matrix: list, mask_matrix: list, data_matrix: list) -> list:
    """Aplică masca peste matricea de date folosind XOR, ignorând zonele rezervate."""
    size = len(qr_matrix)

    for row in range(size):
        for col in range(size):
            if mask_matrix[row][col] is not None:
                qr_matrix[row][col] = data_matrix[row][col] ^ mask_matrix[row][col]

    return qr_matrix

def write_zigzag_data(qr_matrix: list, bitstream: str, version: int) -> list:
    """Populează matricea QR cu șirul de biți, urmărind traseul standard în zigzag."""
    size = len(qr_matrix)
    bit_index = 0
    bitstream_length = len(bitstream)
    going_up = True
    col = size - 1

    while col > 0:
        if col == 6:
            col -= 1

        rows = range(size - 1, -1, -1) if going_up else range(size)

        for row in rows:
            for current_col in (col, col - 1):
                if bit_index == bitstream_length:
                    return qr_matrix

                if not is_reserved_area(row, current_col, size, version):
                    qr_matrix[row][current_col] = int(bitstream[bit_index])
                    bit_index += 1

        going_up = not going_up
        col -= 2

    return qr_matrix

def save_matrix_as_png(qr_matrix: list, filename: str = "output_qr.png", scale: int = 10) -> None:
    """Transformă matricea binară într-o imagine PNG scalată."""
    matrix_array = np.array(qr_matrix, dtype=np.uint8)
    scaled_matrix = np.kron(matrix_array, np.ones((scale, scale), dtype=np.uint8))

    # Maparea culorilor (0 -> 255, 1 -> 0)
    # Folosim .astype(np.uint8) pentru a garanta formatul 8-bit
    pixel_values = ((1 - scaled_matrix) * 255).astype(np.uint8)

    # Generarea și salvarea imaginii pe disc
    Image.fromarray(pixel_values, mode="L").save(filename)
    print(f"\nImaginea QR a fost generată cu succes: '{filename}'")

def determine_qr_version(text_length: int) -> int:
    """
    Calculează cea mai mică versiune QR capabilă să stocheze mesajul.
    Modul Byte folosește: 4 biți (Mod) + 8 biți (Lungime) + 8 biți/caracter.
    """
    required_bits = 4 + 8 + (text_length * 8)

    for version, (capacity_bits, _) in QR_CONFIG_HIGH.items():
        # Verificăm dacă încap datele (lăsăm loc și pentru terminator, deși poate fi trunchiat)
        if required_bits <= capacity_bits:
            return version

    raise ValueError("Textul este prea lung pentru Versiunea 6 (Nivel High).")

def encode_text_to_bitstream(text: str, version: int) -> str:
    """
    Transformă textul într-un șir binar complet conform standardului QR:
    [Mode Indicator] + [Character Count] + [Data] + [Terminator] + [Padding].
    """
    mode_indicator = "0100"  # 0100 reprezintă modul 'Byte'
    char_count = f"{len(text):08b}"  # Convertim lungimea în binar pe 8 biți

    # Transformăm fiecare caracter direct într-un șir binar de 8 biți
    data_bits = "".join(f"{ord(c):08b}" for c in text)

    bitstream = mode_indicator + char_count + data_bits

    capacity_bits = QR_CONFIG_HIGH[version][0]

    # Adăugăm terminatorul (maxim 4 zerouri, dar limitat de capacitatea rămasă)
    remaining_bits = capacity_bits - len(bitstream)
    terminator_length = min(4, remaining_bits)
    if terminator_length > 0:
        bitstream += "0" * terminator_length

    # Bit-padding: rotunjim la cel mai apropiat multiplu de 8 (un byte complet)
    while len(bitstream) % 8 != 0:
        bitstream += "0"

    # Byte-padding: adăugăm biții alternanți 0xEC și 0x11 până umplem versiunea
    pad_index = 0
    while len(bitstream) < capacity_bits:
        bitstream += PADDING_BYTES[pad_index % 2]
        pad_index += 1

    return bitstream

def generate_interleaved_data(bitstream: str, version: int) -> str:
    """
    Împarte datele în blocuri, generează ECC și le 'interleaving' (întrețese)
    conform standardului QR. Returnează șirul final gata de pus în matrice.
    """
    num_blocks, ecc_per_block = QR_BLOCK_CONFIG_HIGH[version]

    # 1. Împărțim bitstream-ul în bytes (pachete de 8 biți)
    data_bytes = [bitstream[i:i + 8] for i in range(0, len(bitstream), 8)]

    # 2. Calculăm dimensiunea blocurilor
    total_data_bytes = len(data_bytes)
    base_size = total_data_bytes // num_blocks
    num_long_blocks = total_data_bytes % num_blocks
    num_short_blocks = num_blocks - num_long_blocks

    # 3. Creăm blocurile de date și blocurile ECC
    data_blocks = []
    ecc_blocks = []
    idx = 0

    for i in range(num_blocks):
        # Standardul spune că blocurile lungi sunt mereu plasate la final
        block_size = base_size + 1 if i >= num_short_blocks else base_size

        # Extragem datele pentru blocul curent
        block_data = data_bytes[idx:idx + block_size]
        data_blocks.append(block_data)
        idx += block_size

        # Generăm ECC pentru acest bloc
        block_bitstream = "".join(block_data)
        ecc_bitstream = generate_ecc_for_block(block_bitstream, ecc_per_block)

        # Împărțim și ECC-ul în bytes
        ecc_bytes = [ecc_bitstream[j:j + 8] for j in range(0, len(ecc_bitstream), 8)]
        ecc_blocks.append(ecc_bytes)

    # 4. Interleaving (Întrețeserea datelor)
    interleaved = []

    # A. Alternăm bytes de date (luăm byte-ul 'i' din fiecare bloc, dacă există)
    max_data_len = base_size + 1
    for i in range(max_data_len):
        for block in data_blocks:
            if i < len(block):
                interleaved.append(block[i])

    # B. Alternăm bytes de ECC (toate blocurile ECC au exact aceeași lungime)
    for i in range(ecc_per_block):
        for block in ecc_blocks:
            interleaved.append(block[i])

    # Unim totul într-un singur șir de biți
    return "".join(interleaved)

def draw_finder_pattern(matrix: list, row_offset: int, col_offset: int) -> None:
    """Desenează un Finder Pattern (7x7) bazat pe distanța față de centru."""
    for r in range(7):
        for c in range(7):
            # Calculăm distanța față de punctul central (3, 3) al pătratului
            dist_r, dist_c = abs(r - 3), abs(c - 3)

            # Pătratul negru exterior (dist == 3), inel alb (dist == 2), centru negru (dist <= 1)
            is_black = max(dist_r, dist_c) != 2
            matrix[row_offset + r][col_offset + c] = 1 if is_black else 0

def draw_alignment_pattern(matrix: list, center_r: int, center_c: int) -> None:
    """Desenează un Alignment Pattern (5x5) în jurul unui centru dat."""
    for r in range(-2, 3):
        for c in range(-2, 3):
            dist_r, dist_c = abs(r), abs(c)
            # Inelul negru exterior (dist == 2), inel alb (dist == 1), pixel central negru (dist == 0)
            is_black = max(dist_r, dist_c) != 1
            matrix[center_r + r][center_c + c] = 1 if is_black else 0

def initialize_qr_matrix(version: int) -> list:
    """
    Creează o matrice QR goală (plină cu 0) și desenează tiparele fixe obligatorii:
    Finder Patterns, Separatoare, Timing Patterns, Alignment Patterns și Dark Module.
    """
    # Preluăm dimensiunea din fișierul de configurare
    size = QR_MATRIX_SIZES[version - 1]
    matrix = [[0 for _ in range(size)] for _ in range(size)]

    # 1. Timing Patterns (liniile punctate care unesc Finder Patterns)
    for i in range(size):
        matrix[6][i] = 1 if i % 2 == 0 else 0
        matrix[i][6] = 1 if i % 2 == 0 else 0

    # 2. Separatoare albe (zone de 8x8 în colțuri pentru a izola Finder-ele)
    for i in range(8):
        for j in range(8):
            matrix[i][j] = 0  # Stânga-Sus
            matrix[i][size - 8 + j] = 0  # Dreapta-Sus
            matrix[size - 8 + i][j] = 0  # Stânga-Jos

    # 3. Desenăm Finder Patterns
    draw_finder_pattern(matrix, 0, 0)  # Stânga-Sus
    draw_finder_pattern(matrix, 0, size - 7)  # Dreapta-Sus
    draw_finder_pattern(matrix, size - 7, 0)  # Stânga-Jos

    # 4. Alignment Patterns (dacă versiunea este >= 2)
    # Refolosim lista elegantă pe care o aveam în config.py!
    if version in ALIGNMENT_PATTERN_COORDS:
        for r, c in ALIGNMENT_PATTERN_COORDS[version]:
            draw_alignment_pattern(matrix, r, c)

    # 5. Dark Module (Un singur pixel negru, fixat mereu la aceste coordonate)
    matrix[size - 8][8] = 1

    return matrix

def generate_mask_matrix(size: int, version: int, mask_id: int) -> list:
    """
    Generează o matrice de mascare (0 sau 1) conform formulelor matematice
    din standardul QR ISO/IEC 18004. Zonele rezervate primesc valoarea None.
    """
    # Spunem explicit că matricea conține elemente de tip (int sau None)
    mask: list[list[int | None]] = [[0 for _ in range(size)] for _ in range(size)]

    for r in range(size):
        for c in range(size):
            # Dacă e zonă rezervată, nu aplicăm masca pe acest pixel
            if is_reserved_area(r, c, size, version):
                mask[r][c] = None
                continue

            # Formulele matematice ISO pentru cele 8 măști standard
            if mask_id == 0:
                val = (r + c) % 2 == 0
            elif mask_id == 1:
                val = r % 2 == 0
            elif mask_id == 2:
                val = c % 3 == 0
            elif mask_id == 3:
                val = (r + c) % 3 == 0
            elif mask_id == 4:
                val = (r // 2 + c // 3) % 2 == 0
            elif mask_id == 5:
                val = ((r * c) % 2) + ((r * c) % 3) == 0
            elif mask_id == 6:
                val = (((r * c) % 2) + ((r * c) % 3)) % 2 == 0
            elif mask_id == 7:
                val = (((r + c) % 2) + ((r * c) % 3)) % 2 == 0
            else:
                val = False

            mask[r][c] = int(val)

    return mask

def add_quiet_zone(matrix: list) -> list:
    """Adaugă marginea albă obligatorie de 4 module (Quiet Zone) în jurul matricei."""
    padded_matrix = []

    # 4 rânduri complet albe sus
    empty_row = [0] * (len(matrix) + 8)
    for _ in range(4):
        padded_matrix.append(empty_row.copy())

    # Adăugăm 4 zerouri la stânga, rândul original, și 4 zerouri la dreapta
    for row in matrix:
        padded_matrix.append([0] * 4 + row + [0] * 4)

    # 4 rânduri complet albe jos
    for _ in range(4):
        padded_matrix.append(empty_row.copy())

    return padded_matrix

def calculate_penalty_rule_1(matrix: list) -> int:
    """Regula 1: 5 sau mai multe module consecutive de aceeași culoare (pe rânduri și coloane)."""
    penalty = 0

    # 1. Verificăm rândurile
    for row in matrix:
        for _, group in itertools.groupby(row):
            length = len(list(group))
            if length >= 5:
                penalty += (length - 2)

    # 2. Verificăm coloanele (transpunem matricea cu zip)
    for col in zip(*matrix):
        for _, group in itertools.groupby(col):
            length = len(list(group))
            if length >= 5:
                penalty += (length - 2)

    return penalty

def calculate_penalty_rule_2(matrix: list) -> int:
    """Regula 2: Blocuri de 2x2 module de aceeași culoare (penalizare 3 puncte per bloc)."""
    penalty = 0
    size = len(matrix)

    for r in range(size - 1):
        for c in range(size - 1):
            # Python știe să evalueze lanțuri de egalități!
            if matrix[r][c] == matrix[r][c + 1] == matrix[r + 1][c] == matrix[r + 1][c + 1]:
                penalty += 3

    return penalty

def calculate_penalty_rule_3(padded_matrix: list) -> int:
    """
    Calculează Penalizarea #3: Secvențe care seamănă cu Finder Pattern-ul.
    Caută '000010111010' și '010111010000' pe rânduri și coloane.
    Notă: Matricea trebuie să includă deja 'Quiet Zone' (marginea de 4 module albe).
    """
    pattern1 = "000010111010"
    pattern2 = "010111010000"
    penalty_occurrences = 0

    # 1. Căutare pe orizontală (rânduri)
    for row in padded_matrix:
        # Transformăm [0, 0, 1, 0, 1...] în '00101...'
        row_str = "".join(map(str, row))
        penalty_occurrences += row_str.count(pattern1)
        penalty_occurrences += row_str.count(pattern2)

    # 2. Căutare pe verticală (coloane)
    # zip(*padded_matrix) ia fiecare coloană și o transformă într-un rând!
    for col in zip(*padded_matrix):
        col_str = "".join(map(str, col))
        penalty_occurrences += col_str.count(pattern1)
        penalty_occurrences += col_str.count(pattern2)

    # Standardul dictează înmulțirea cu 40 pentru fiecare apariție
    return penalty_occurrences * 40

def calculate_penalty_rule_4(matrix: list) -> int:
    """Regula 4: Proporția de module negre (penalizare de 10 pct la fiecare 5% deviație de la 50%)."""
    total_modules = len(matrix) * len(matrix)

    # Numărăm câți de '1' (module negre) sunt în toată matricea
    dark_modules = sum(row.count(1) for row in matrix)

    # Calculăm procentajul
    percent_dark = (dark_modules / total_modules) * 100

    # Aflăm abaterea față de 50%, și o împărțim în trepte de 5%
    deviation = abs(percent_dark - 50)
    penalty = int(deviation // 5) * 10

    return penalty

def calculate_total_penalty_score(matrix: list) -> int:
    """Orchestratorul care adună toate cele 4 penalizări ISO."""
    score = 0
    score += calculate_penalty_rule_1(matrix)
    score += calculate_penalty_rule_2(matrix)

    # Pentru regula 3, creăm o copie cu Quiet Zone
    padded_matrix = add_quiet_zone(matrix)
    score += calculate_penalty_rule_3(padded_matrix)

    score += calculate_penalty_rule_4(matrix)
    return score

def scriere_cod_qr():
    print("\n--- Modul Generare QR ---")
    text = input("Șirul de caractere pe care dorești să-l transformi: ").strip()

    fisier = input("Numele fișierului de output (ex: qrcode.png): ").strip()

    while not fisier.endswith(".png") or fisier.startswith("."):
        print("Eroare: Fișierul trebuie să aibă extensia '.png' și un nume valid.")
        fisier = input("Numele fișierului de output: ").strip()

    # 1. Determinăm versiunea și facem encoding mesajul
    try:
        version = determine_qr_version(len(text))
        print(f"Versiune detectată: {version} (Nivel ECC: High)")
    except ValueError as e:
        print(f"Eroare: {e}")
        return

    bitstream = encode_text_to_bitstream(text, version)

    # 2. Împărțirea pe blocuri, generarea ECC și Interleaving
    final_bitstream = generate_interleaved_data(bitstream, version)

    # 3. Construirea Matricei și Adăugarea Tiparelor Fixe
    qr_matrix = initialize_qr_matrix(version)
    size = len(qr_matrix)

    # 4. Scriem datele (zigzag) în matrice
    qr_matrix_with_data = write_zigzag_data(qr_matrix, final_bitstream, version)

    # 5. Aplicarea măștilor și găsirea celei mai bune
    min_puncte = float('inf')
    masca_potrivita = 0
    best_final_matrix = []

    print("Evaluăm măștile pentru cel mai bun contrast...")

    for m in range(8):
        # Facem o copie curată a matricei brute pe care să testăm
        test_matrix = copy.deepcopy(qr_matrix_with_data)

        # Generăm și aplicăm masca 'm'
        mask_matrix = generate_mask_matrix(size, version, m)
        test_matrix = apply_mask(test_matrix, mask_matrix, qr_matrix_with_data)

        # Adăugăm biții de format pentru această mască specifică
        format_bits = generate_format_string(m)
        test_matrix = apply_format_bits(test_matrix, format_bits)

        # Calculăm punctajul total folosind orchestratorul nostru curat
        score = calculate_total_penalty_score(test_matrix)

        # Salvăm cea mai bună mască
        if score < min_puncte:
            min_puncte = score
            masca_potrivita = m
            best_final_matrix = copy.deepcopy(test_matrix)

    print(f"Masca câștigătoare este Masca {masca_potrivita} (Scor Penalizare: {min_puncte})")

    # 6. Crearea imaginii finale
    # Adăugăm marginea albă (Quiet Zone) necesară pentru scanare
    final_image_matrix = add_quiet_zone(best_final_matrix)

    # Salvăm imaginea scalată de 20 de ori pentru claritate maximă
    save_matrix_as_png(final_image_matrix, fisier, scale=20)
