import os
from PIL import Image

# Importăm din fișierele noastre:
from config import QR_BIT_LENGTHS, QR_MATRIX_SIZES, QR_CONFIG_HIGH
from utils import detect_qr_scale, scale_down, is_reserved_area

def get_mask_id(matrix):
    # Transformăm lista [1, 1, 0] în string-ul "110"
    bits_str = f"{matrix[8][2]}{matrix[8][3]}{matrix[8][4]}"

    # Valoarea binară complementară (formula din standardul QR)
    return 7 - int(bits_str, 2)

def remove_mask(matrix, mask_id, version):
    size = len(matrix)
    for i in range(size):
        for j in range(size):
            # Dacă nu este zonă rezervată, testăm masca
            if not is_reserved_area(i, j, size, version):
                apply = False

                if mask_id == 0:
                    apply = (j % 3 == 0)
                elif mask_id == 1:
                    apply = ((i + j) % 3 == 0)
                elif mask_id == 2:
                    apply = ((i + j) % 2 == 0)
                elif mask_id == 3:
                    apply = (i % 2 == 0)
                elif mask_id == 4:
                    apply = (((i * j) % 3 + i * j) % 2 == 0)
                elif mask_id == 5:
                    apply = (((i * j) % 3 + i + j) % 2 == 0)
                elif mask_id == 6:
                    apply = ((i // 2 + j // 3) % 2 == 0)
                elif mask_id == 7:
                    apply = (((i * j) % 2 + (i * j) % 3) == 0)

                if apply:
                    matrix[i][j] ^= 1

    return matrix

def extract_qr_bits(matrix, size, version):
    qr_bits = []
    going_up = True

    col = size - 1

    while col > 0:
        # Standardul QR: coloana 6 este rezervată pentru Vertical Timing Pattern
        if col == 6:
            col -= 1

        # Determinăm intervalul de rânduri în funcție de direcție
        rows = range(size - 1, -1, -1) if going_up else range(size)

        for row in rows:
            # Citim cele două coloane din banda curentă (dreapta, apoi stânga)
            for current_col in (col, col - 1):
                if not is_reserved_area(row, current_col, size, version):
                    qr_bits.append(matrix[row][current_col])

        # Schimbăm direcția și trecem la următoarea bandă de 2 coloane
        going_up = not going_up
        col -= 2

    return "".join(map(str, qr_bits))

def remove_ecc_and_get_version(bitstring):
    # Format: versiune: (data_bits, total_bytes)
    qr_config_high = {
        1: (72, 26),
        2: (128, 44),
        3: (208, 70),
        4: (288, 100),
        5: (368, 134),
        6: (480, 172),
    }

    input_byte_count = len(bitstring) // 8

    for version, (data_bits, total_bytes) in qr_config_high.items():
        if total_bytes == input_byte_count:
            # Returnăm biții de date și versiunea detectată
            return bitstring[:data_bits], version

    # Dacă nu am găsit nicio potrivire în tabelul nostru
    print(f"Eroare: Lungimea de {input_byte_count} bytes nu corespunde versiunilor 1-6 (Nivel High).")
    return None, None

def rearrange_qr_data(bitstream, version):
    # Versiunile 1 și 2 au un singur bloc, deci nu necesită rearanjare
    if version <= 2:
        return bitstream

    # Împărțim șirul de biți în bytes (grupuri de câte 8 biți)
    byte_list = [bitstream[i:i + 8] for i in range(0, len(bitstream), 8)]

    # Mapăm versiunea la numărul de blocuri corespunzător
    blocks_count_map = {3: 2, 4: 4, 5: 4, 6: 4}
    num_blocks = blocks_count_map.get(version, 4)

    # Inițializăm lista de blocuri (ex: [[], [], [], []])
    blocks = [[] for _ in range(num_blocks)]

    # Distribuim bytes în blocuri folosind tehnica interleaving
    for i, byte in enumerate(byte_list):
        # Caz particular pentru Versiunea 5 (distribuție asimetrică a bytes)
        if version == 5:
            if i == 44:
                blocks[2].append(byte)
            elif i == 45:
                blocks[3].append(byte)
            else:
                blocks[i % 4].append(byte)
        else:
            # Distribuție standard (Round Robin)
            blocks[i % num_blocks].append(byte)

    # Reconstruim șirul final prin concatenarea blocurilor
    return "".join("".join(block) for block in blocks)

def decode_qr_message(bitstream):
    # 1. Eliminăm padding-ul de la final (11101100 și 00010001)
    # Împărțim șirul în bytes (8 biți)
    bytes_list = [bitstream[i:i + 8] for i in range(0, len(bitstream), 8)]

    # Cât timp ultimul byte din listă este un byte de padding, îl scoatem
    while bytes_list and bytes_list[-1] in ("11101100", "00010001"):
        bytes_list.pop()

    clean_bitstream = "".join(bytes_list)

    # 2. Slicing direct pentru a elimina metadatele
    # Structura QR pe care o curățăm este:
    # [Mode: 4 biți] [Char Count: 8 biți] [Mesaj: X biți] [Terminator: 4 biți]

    # Ne asigurăm- că avem suficientă lungime pentru a nu primi o eroare
    if len(clean_bitstream) >= 16:
        # Tăiem primii 12 biți (4 Mode + 8 Count) și ultimii 4 biți (Terminator)
        actual_data_bits = clean_bitstream[12:-4]
    else:
        return ""

    # 3. Conversia finală din Binar în String
    # Împărțim biții rămași în caractere de 8 biți
    message_bytes = [actual_data_bits[i:i + 8] for i in range(0, len(actual_data_bits), 8)]

    # Folosim chr(int(b, 2)) pentru conversie, dar ignorăm resturile
    # (ex: dacă rămân 2-3 biți de zero la final din cauza alinierii)
    decoded_message = "".join(chr(int(b, 2)) for b in message_bytes if len(b) == 8)

    print(decoded_message)
    return decoded_message

def citire_cod_qr():
    print("\n--- Modul Citire QR ---")
    fisier = input("Fișierul pe care dorești să îl scanezi: ").strip()

    if not os.path.exists(fisier):
        print(f"Eroare: Fișierul '{fisier}' nu există.")
        return

    # 1. Preprocesare Imagine
    scale = detect_qr_scale(fisier)
    img_mica = scale_down(fisier, scale)
    width, height = img_mica.size
    pixels = list(img_mica.getdata())

    # Construire matrice binară
    qr_matrix = [
        [0 if pixels[i * width + j] == 255 else 1 for j in range(width)]
        for i in range(height)
    ]

    # 2. Validare Versiune
    try:
        version_index = QR_MATRIX_SIZES.index(height)
        version = version_index + 1
        dim_versiune = QR_BIT_LENGTHS[version_index]
    except ValueError:
        print(f"Eroare: Dimensiunea matricei ({height}x{height}) este invalidă sau versiunea > 6.")
        return

    # 3. Prelucrare Matrice
    mask_id = get_mask_id(qr_matrix)
    qr_matrix = remove_mask(qr_matrix, mask_id, version)

    # 4. Extragere și Decodare Date
    qr_bits = extract_qr_bits(qr_matrix, height, dim_versiune, version)

    data_bits, detected_version = remove_ecc_and_get_version(qr_bits)

    if data_bits is not None:
        rearranged_data = rearrange_qr_data(data_bits, detected_version)
        print("\nMesaj Decodat:")
        decode_qr_message(rearranged_data)