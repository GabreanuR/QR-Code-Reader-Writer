import numpy as np
from PIL import Image
import reedsolo

from config import QR_BIT_LENGTHS, QR_MATRIX_SIZES
from utils import is_reserved_area

def generate_format_string(mask_id):
    """
    Generează șirul de 15 biți pentru Format Information.
    Include nivelul de eroare (High - '10'), ID-ul măștii și codul BCH(15, 5).
    """
    ecc_level = "10"  # Hardcodat pentru nivelul H (High)
    mask_bin = f"{mask_id:03b}"
    format_bits = ecc_level + mask_bin

    # Polinom generator pentru BCH (15, 5): x^10 + x^8 + x^5 + x^4 + x^2 + x + 1
    generator = 0b10100110111

    # Facem spațiu (shiftare cu 10 biți) pentru a adăuga restul BCH
    info = int(format_bits, 2) << 10

    # Calculăm restul împărțirii polinomiale
    for i in range(5):  # Avem exact 5 biți în format_bits
        if info & (1 << (14 - i)):
            info ^= generator << (4 - i)

    bch_bits = info & 0b1111111111

    # Combinăm biții și aplicăm XOR cu masca standard QR pentru zona de format
    final_format = (int(format_bits, 2) << 10 | bch_bits) ^ 0b101010000010010

    return f"{final_format:015b}"

def generate_ecc_for_block(data_bits, ecc_capacity):
    """
    Generează biții de Error Correction (ECC) pentru un bloc de date
    folosind algoritmul Reed-Solomon.
    """
    # Inițializăm codecul cu numărul de bytes de corecție necesari
    rs = reedsolo.RSCodec(ecc_capacity)

    # Convertim string-ul de biți ('10101010...') într-un bytearray nativ Python
    data_bytes = bytearray(int(data_bits[i:i + 8], 2) for i in range(0, len(data_bits), 8))

    # rs.encode returnează [Date Originale + Biți ECC]
    encoded_data = rs.encode(data_bytes)

    # Extragem strict partea de ECC de la final
    ecc_bytes = encoded_data[len(data_bytes):]

    # Convertim bytearray-ul înapoi într-un șir de biți formatat cu 0-uri în față
    return "".join(format(byte, '08b') for byte in ecc_bytes)

def apply_mask(qr_matrix, mask_matrix, data_matrix):
    size = len(qr_matrix)

    for row in range(size):
        for col in range(size):
            if mask_matrix[row][col] is not None:
                # Aplicăm XOR (^) între datele originale și mască
                qr_matrix[row][col] = data_matrix[row][col] ^ mask_matrix[row][col]

    return qr_matrix

def write_zigzag_data(qr_matrix, bitstream, version):
    size = len(qr_matrix)
    bit_index = 0
    bitstream_length = len(bitstream)
    going_up = True

    # Pornim de la ultima coloană (dreapta-jos)
    col = size - 1

    while col > 0:
        # Standardul QR: coloana 6 este rezervată
        if col == 6:
            col -= 1

        # Generăm rândurile în funcție de direcție
        rows = range(size - 1, -1, -1) if going_up else range(size)

        for row in rows:
            for current_col in (col, col - 1):
                # Dacă am scris toți biții, returnăm matricea
                if bit_index == bitstream_length:
                    return qr_matrix

                # Verificăm zonele
                if not is_reserved_area(row, current_col, size, version):
                    qr_matrix[row][current_col] = int(bitstream[bit_index])
                    bit_index += 1

        # Schimbăm direcția și trecem la următoarea bandă
        going_up = not going_up
        col -= 2

    return qr_matrix

def save_matrix_as_png(qr_matrix, filename="output_qr.png", scale=10):
    # 1. Convertim lista nativă Python într-un array NumPy pentru performanță
    matrix_array = np.array(qr_matrix, dtype=np.uint8)

    # 2. Scalăm matricea: fiecare '1' sau '0' devine un bloc de (scale x scale)
    # np.kron este excepțional de eficient aici, evitând buclele for
    scaled_matrix = np.kron(matrix_array, np.ones((scale, scale), dtype=np.uint8))

    # 3. Maparea culorilor:
    # În logica noastră: 1 = modul negru, 0 = modul alb.
    # În standardul Pillow (modul 'L'): 0 = Negru absolut, 255 = Alb absolut.
    pixel_values = (1 - scaled_matrix) * 255

    # 4. Generarea și salvarea imaginii pe disc
    Image.fromarray(pixel_values, mode="L").save(filename)

    print(f"\nImaginea QR a fost generată cu succes: '{filename}'")

def scriere_cod_qr():
    print()
    secv = input("Sirul de caractere ce doresti a transforma in cod QR: ")
    secv = secv.strip()

    fisier = input("Fisiere de output: ")
    while fisier.endswith(".png") == False or fisier[0] == ".":
        print("Fisierul trebuie sa se termine cu \".png\" ")
        fisier = input("Fisiere de output: ")

    # din https://www.nayuki.io/page/creating-a-qr-code-step-by-step

    # Ce versiune sa folosim? (Error correction high)

    # Max V6
    VE = [0, 9, 16, 26, 36, 46, 60]  # Capacitatile in functie de versiune
    VECC = [0, 17, 28, 22, 16, 22, 28]  # ECC urile in functie de versiune
    VnrB = [0, 1, 1, 2, 4, 4, 4]  # Numarul de blocuri in functie de versiune
    VQRSize = [0, 21, 25, 29, 33, 37, 41]  # Marimea matricei QR in functie de versiune

    # 1. Create data segment
    secv = list(secv)
    for i in range(len(secv)):
        # tranformam fiecare caracter in cod ascii
        secv[i] = ord(secv[i])
        # transformam fiecare cod ascii in binar
        secv[i] = bin(secv[i])

    # 2.Fit to version number
    # Segment 0 count
    segmlen = len(secv)
    segmlen = bin(segmlen)

    # 3. Concatenate segments, add padding, make codewords
    Segment_0_mode = "0100"  # corespunde modului byte
    segmlen = str(segmlen)
    segmlen = segmlen[2:]
    while len(segmlen) < 8:
        segmlen = "0" + segmlen

    Segment_0_data = ""

    for i in secv:
        aux = str(i)
        aux = aux[2:]
        aux = aux.zfill(8)
        Segment_0_data = Segment_0_data + aux

    terminator = "0000"

    nr_pana_acum = Segment_0_mode + segmlen + Segment_0_data + terminator

    aux = len(nr_pana_acum)
    while aux % 8 != 0:
        nr_pana_acum += "0"
        aux = len(nr_pana_acum)
        print("DA")

    aux = aux // 8  # nr de caractere curente

    for i in range(len(VE)):
        if aux > VE[i]:
            vs = i
        else:
            vs = i
            break

    capacitate = VE[vs]
    Byte_padding = capacitate - aux

    auxEC = "11101100"
    aux11 = "00010001"

    while Byte_padding != 0:
        nr_pana_acum += auxEC
        Byte_padding -= 1
        if Byte_padding == 0:
            break
        nr_pana_acum += aux11
        Byte_padding -= 1

    # 4. Split blocks, add ECC, interleave

    nrBlocuri = VnrB[vs]

    nrDataCodeWords = len(nr_pana_acum) // 8
    dataCdWdperLB = nrDataCodeWords // 4 + 1  # Data codewords per long block

    if nrDataCodeWords % nrBlocuri != 0:
        dataCdWdperLB = nrDataCodeWords // nrBlocuri + 1  # Data codewords per long block
        dataCdWdperSB = dataCdWdperLB - 1  # Data codewords per short block
    else:
        dataCdWdperLB = nrDataCodeWords // nrBlocuri  # Data codewords per long block
        dataCdWdperSB = dataCdWdperLB

    aux = nrDataCodeWords % nrBlocuri
    if aux == 0:
        nrLB = nrBlocuri  # Nr Long Blocks
        nrSB = 0  # Nr Short Blocks
        copnrLB = nrLB
        copnrSB = nrSB
    else:
        nrLB = aux
        copnrLB = nrLB
        nrSB = nrBlocuri - aux
        copnrSB = nrSB

    nr_pana_acum = list(nr_pana_acum)

    for i in range(0, len(nr_pana_acum), 8):
        nr_pana_acum[i] = "".join(nr_pana_acum[i:i + 8])

    while "0" in nr_pana_acum:
        nr_pana_acum.remove("0")
    while "1" in nr_pana_acum:
        nr_pana_acum.remove("1")

    M = []  # matricea in care stocam datele

    for i in range(len(nr_pana_acum)):
        M.append(nr_pana_acum[i])

    i = 0
    while copnrSB != 0:
        x = "".join(M[i:i + dataCdWdperSB])
        M[i:i + dataCdWdperSB] = [x]
        i += 1
        copnrSB -= 1
    while copnrLB != 0:
        x = "".join(M[i:i + dataCdWdperLB])
        M[i:i + dataCdWdperLB] = [x]
        i += 1
        copnrLB -= 1

    for i in range(len(M)):
        M[i] = [M[i], []]

    generare_ecc(M, VECC[vs])

    for i in range(len(M)):
        for j in range(0, len(M[i])):
            M[i][j] = list(M[i][j])
            for k in range(0, len(M[i][j]), 8):
                M[i][j][k] = "".join(M[i][j][k:k + 8])
            while "0" in M[i][j]:
                M[i][j].remove("0")
            while "1" in M[i][j]:
                M[i][j].remove("1")

    M2 = []  # Matricea cu elementele reasezate

    copnrLB = nrLB
    copnrSB = nrSB - 1

    if dataCdWdperLB != dataCdWdperSB:
        while copnrSB != -1:
            M[copnrSB][0].append(None)
            copnrSB -= 1

    for i in range(0, len(M)):
        M[i] = M[i][0] + M[i][1]

    M2 = [[M[j][i] for j in range(len(M))] for i in range(len(M[0]))]

    for i in range(len(M2)):
        while None in M2[i]:
            M2[i].remove(None)

    M3 = [elem for linie in M2 for elem in linie]  # Lista cu elemente
    M3 = "".join(M3)
    M3 = list(M3)
    for i in range(len(M3)):
        M3[i] = int(M3[i])

    # 5. Draw fixed patterns

    QR = [[0 for _ in range(VQRSize[vs])] for _ in range(VQRSize[vs])]

    for i in range(VQRSize[vs]):
        if i % 2 == 0:
            QR[i][6] = 1
            QR[6][i] = 1

    # Coltul stanga sus

    for i in range(8):
        for j in range(8):
            QR[i][j] = 0

    for i in range(7):
        for j in range(7):
            QR[i][j] = 1

    for i in range(1, 6):
        for j in range(1, 6):
            QR[i][j] = 0

    for i in range(2, 5):
        for j in range(2, 5):
            QR[i][j] = 1

    # Coltul dreapta sus

    aux = len(QR)

    for i in range(8):
        for j in range(aux - 8, aux):
            QR[i][j] = 0

    for i in range(7):
        for j in range(aux - 7, aux):
            QR[i][j] = 1

    for i in range(1, 6):
        for j in range(aux - 6, aux - 1):
            QR[i][j] = 0

    for i in range(2, 5):
        for j in range(aux - 5, aux - 2):
            QR[i][j] = 1

    # Coltul stanga jos

    for i in range(aux - 8, aux):
        for j in range(8):
            QR[i][j] = 0

    for i in range(aux - 7, aux):
        for j in range(7):
            QR[i][j] = 1

    for i in range(aux - 6, aux - 1):
        for j in range(1, 6):
            QR[i][j] = 0

    for i in range(aux - 5, aux - 2):
        for j in range(2, 5):
            QR[i][j] = 1

    # patrat dreapta jos

    if vs >= 2:
        for i in range(aux - 9, aux - 4):
            for j in range(aux - 9, aux - 4):
                QR[i][j] = 1

        for i in range(aux - 8, aux - 5):
            for j in range(aux - 8, aux - 5):
                QR[i][j] = 0

        QR[aux - 7][aux - 7] = 1

    QR[aux - 8][8] = 1
    # 6. Draw codewords and remainder

    QR = write_zigzag_data(QR, M3)
    # for linie in QR:
    # print(*QR)

    # 7. Try applying each mask

    Lista_masti = [[], [], [], [], [], [], [], []]
    for i in range(len(Lista_masti)):
        Lista_masti[i] = [[0 for _ in range(VQRSize[vs])] for _ in range(VQRSize[vs])]

        for j in range(VQRSize[vs]):
            Lista_masti[i][j][6] = None
            Lista_masti[i][6][j] = None

        # Coltul stanga sus

        for j in range(9):
            for k in range(9):
                Lista_masti[i][j][k] = None

        # Coltul dreapta sus

        aux = len(Lista_masti[i])

        for j in range(9):
            for k in range(aux - 8, aux):
                Lista_masti[i][j][k] = None

        # Coltul stanga jos

        for j in range(aux - 8, aux):
            for k in range(9):
                Lista_masti[i][j][k] = None

        # patrat dreapta jos

        if vs >= 2:
            for j in range(aux - 9, aux - 4):
                for k in range(aux - 9, aux - 4):
                    Lista_masti[i][j][k] = None

    # MASCA 0

    for i in range(len(Lista_masti[0])):
        for j in range(len(Lista_masti[0][i])):
            if Lista_masti[0][i][j] != None:
                if (i + j) % 2 == 0:
                    Lista_masti[0][i][j] = 1

    # MASCA 1

    for i in range(len(Lista_masti[1])):
        for j in range(len(Lista_masti[1][i])):
            if Lista_masti[1][i][j] != None:
                if i % 2 == 0:
                    Lista_masti[1][i][j] = 1

    # MASCA 2

    for i in range(len(Lista_masti[2])):
        for j in range(len(Lista_masti[2][i])):
            if Lista_masti[2][i][j] != None:
                if j % 3 == 0:
                    Lista_masti[2][i][j] = 1

    # MASCA 3

    for i in range(len(Lista_masti[3])):
        for j in range(len(Lista_masti[3][i])):
            if Lista_masti[3][i][j] != None:
                if (i + j) % 3 == 0:
                    Lista_masti[3][i][j] = 1

    # MASCA 4

    for i in range(len(Lista_masti[4])):
        for j in range(len(Lista_masti[4][i])):
            if Lista_masti[4][i][j] != None:
                if (
                        ((i % 4 == 0 or i % 4 == 1) and (j % 6 == 0 or j % 6 == 1 or j % 6 == 2))
                        or
                        ((i % 4 == 2 or i % 4 == 3) and (j % 6 == 3 or j % 6 == 4 or j % 6 == 5))
                ):
                    Lista_masti[4][i][j] = 1

    # MASCA 5

    for i in range(len(Lista_masti[5])):
        for j in range(len(Lista_masti[5][i])):
            if Lista_masti[5][i][j] != None:
                if (
                        ((i % 6 == 0) or (j % 6 == 0))
                        or
                        (i % 2 == 0 and (j - 3) % 6 == 0)
                        or
                        (j % 2 == 0 and (i - 3) % 6 == 0)
                ):
                    Lista_masti[5][i][j] = 1

    # MASCA 6

    for i in range(len(Lista_masti[6])):
        for j in range(len(Lista_masti[6][i])):
            if Lista_masti[6][i][j] != None:
                if (
                        ((i % 6 == 0) or (j % 6 == 0))
                        or
                        (i % 2 == 0 and (j - 3) % 6 == 0)
                        or
                        (j % 2 == 0 and (i - 3) % 6 == 0)
                        or
                        ((i + j + 3) % 6 == 0)
                        or
                        ((i + 1) % 6 == 0 and (j + 1) % 6 == 0)
                        or
                        ((i - 1) % 6 == 0 and (j - 1) % 6 == 0)
                        or
                        ((i - 4) % 6 == 0 and (j - 2) % 6 == 0)
                        or
                        ((i - 2) % 6 == 0 and (j - 4) % 6 == 0)

                ):
                    Lista_masti[6][i][j] = 1

    # MASCA 7

    for i in range(len(Lista_masti[7])):
        for j in range(len(Lista_masti[7][i])):
            if Lista_masti[7][i][j] != None:
                if (
                        ((i + j) % 6 == 0)
                        or
                        ((i - j - 2) % 6 == 0)
                        or
                        ((i - j + 2) % 6 == 0)
                        or
                        ((i - j - 3) % 6 == 0 and (i % 3) != 0)
                ):
                    Lista_masti[7][i][j] = 1

    min_puncte = 100000
    min_puncte = 1000000
    # verificam criteriile pentru alegerea mastii
    cop_QR = [[0 for _ in range(VQRSize[vs])] for _ in range(VQRSize[vs])]
    for i in range(VQRSize[vs]):
        for j in range(VQRSize[vs]):
            cop_QR[i][j] = QR[i][j]
    for m in range(8):

        QR = apply_mask(QR, Lista_masti[m], cop_QR)

        masca = m

        biti = creare_format(masca)

        QR = format_in_qr(QR, biti)

        puncte_secvente = 0
        nr = 0  # nr secvente total
        secv_act = 1
        secv_act_1 = 1
        for i in range(VQRSize[vs]):
            secv_act = 1
            secv_act_1 = 1
            for j in range(1, VQRSize[vs]):
                # pentru orizontala
                if QR[i][j] == QR[i][j - 1]:
                    secv_act += 1
                else:
                    if secv_act >= 5:
                        puncte_secvente += (secv_act - 2)
                        nr += 1
                    secv_act = 1
                # paralel pentru verticala
                if QR[j][i] == QR[j - 1][i]:
                    secv_act_1 += 1
                else:
                    if secv_act_1 >= 5:
                        puncte_secvente += (secv_act_1 - 2)
                        nr += 1
                    secv_act_1 = 1

            if secv_act >= 5:
                puncte_secvente += (secv_act - 2)
                nr += 1
            if secv_act_1 >= 5:
                puncte_secvente += (secv_act_1 - 2)
                nr += 1

        nr_boxuri = 0
        for i in range(VQRSize[vs] - 1):
            for j in range(VQRSize[vs] - 1):
                if QR[i][j] == QR[i + 1][j + 1] and QR[i + 1][j] == QR[i][j + 1] and QR[i][j] == QR[i][j + 1]:
                    nr_boxuri += 1
        nr_boxuri = nr_boxuri * 3

        copie_qr = [[0 for _ in range((VQRSize[vs] + 8))] for _ in range((VQRSize[vs] + 8))]
        for i in range(VQRSize[vs]):
            for j in range(VQRSize[vs]):
                copie_qr[i + 4][j + 4] = QR[i][j]

        finding_pat = 0
        for i in range((VQRSize[vs] + 4)):
            for j in range((VQRSize[vs] - 3)):
                # 0 0 0 0 1 0 1 1 1 0 1 0 - pattern

                # pe linie
                if copie_qr[i][j] == 0 and copie_qr[i][j + 1] == 0 and copie_qr[i][j + 2] == 0 and copie_qr[i][
                    j + 3] == 0 and copie_qr[i][j + 4] == 1 and copie_qr[i][j + 5] == 0 and copie_qr[i][j + 6] == 1 and \
                        copie_qr[i][j + 7] == 1 and copie_qr[i][j + 8] == 1 and copie_qr[i][j + 9] == 0 and copie_qr[i][
                    j + 10] == 1 and copie_qr[i][j + 11] == 0:
                    finding_pat += 1


                elif copie_qr[i][j] == 0 and copie_qr[i][j + 1] == 1 and copie_qr[i][j + 2] == 0 and copie_qr[i][
                    j + 3] == 1 and copie_qr[i][j + 4] == 1 and copie_qr[i][j + 5] == 1 and copie_qr[i][j + 6] == 0 and \
                        copie_qr[i][j + 7] == 1 and copie_qr[i][j + 8] == 0 and copie_qr[i][j + 9] == 0 and copie_qr[i][
                    j + 10] == 0 and copie_qr[i][j + 11] == 0:
                    finding_pat += 1

                ###pe coloana
                if copie_qr[j][i] == 0 and copie_qr[j + 1][i] == 0 and copie_qr[j + 2][i] == 0 and copie_qr[j + 3][
                    i] == 0 and copie_qr[j + 4][i] == 1 and copie_qr[j + 5][i] == 0 and copie_qr[j + 6][i] == 1 and \
                        copie_qr[j + 7][i] == 1 and copie_qr[j + 8][i] == 1 and copie_qr[j + 9][i] == 0 and \
                        copie_qr[j + 10][i] == 1 and copie_qr[j + 11][i] == 0:
                    finding_pat += 1

                elif copie_qr[j][i] == 0 and copie_qr[j + 1][i] == 1 and copie_qr[j + 2][i] == 0 and copie_qr[j + 3][
                    i] == 1 and copie_qr[j + 4][i] == 1 and copie_qr[j + 5][i] == 1 and copie_qr[j + 6][i] == 0 and \
                        copie_qr[j + 7][i] == 1 and copie_qr[j + 8][i] == 0 and copie_qr[j + 9][i] == 0 and \
                        copie_qr[j + 10][i] == 0 and copie_qr[j + 11][i] == 0:
                    finding_pat += 1
        finding_pat *= 40

        nr_1 = 0
        nr_0 = 1
        for i in range(VQRSize[vs]):
            for j in range(VQRSize[vs]):
                if QR[i][j] == 1:
                    nr_1 += 1
        dim_total = VQRSize[vs] ** 2

        proportie_biti_1 = 100 * float(nr_1) / float(dim_total)
        if proportie_biti_1 > 45 and proportie_biti_1 < 55:
            pct_prop = 0
        elif proportie_biti_1 >= 40 and proportie_biti_1 <= 60:
            pct_prop = 10
        elif proportie_biti_1 >= 35 and proportie_biti_1 <= 65:
            pct_prop = 20
        elif proportie_biti_1 >= 30 and proportie_biti_1 <= 70:
            pct_prop = 30
        elif proportie_biti_1 >= 25 and proportie_biti_1 <= 75:
            pct_prop = 40
        elif proportie_biti_1 >= 20 and proportie_biti_1 <= 80:
            pct_prop = 50
        elif proportie_biti_1 >= 15 and proportie_biti_1 <= 85:
            pct_prop = 60
        elif proportie_biti_1 >= 10 and proportie_biti_1 <= 90:
            pct_prop = 70
        elif proportie_biti_1 >= 5 and proportie_biti_1 <= 95:
            pct_prop = 80
        elif proportie_biti_1 >= 0 and proportie_biti_1 <= 100:
            pct_prop = 90

        total_puncte = puncte_secvente + nr_boxuri + finding_pat + pct_prop
        # am aflat punctele per masca, o alegem daca e buna in momentul actual
        if min_puncte > total_puncte:
            min_puncte = total_puncte
            masca_potrivita = m

    QR = apply_mask(cop_QR, Lista_masti[masca_potrivita], cop_QR)

    masca = masca_potrivita

    biti = creare_format(masca)

    QR = format_in_qr(QR, biti)

    save_matrix_as_png(QR, fisier, 20)

    return

