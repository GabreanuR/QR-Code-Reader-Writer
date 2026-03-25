"""
Configurația centrală pentru Scan Gogh (Generator & Reader).
Conține specificațiile standardului ISO pentru codurile QR, 
inclusiv dimensiuni, capacități de date și polinoame matematice
pentru Versiunile 1-6 (Nivel de eroare: HIGH).
"""
# ==========================================
# 1. DIMENSIUNI ȘI CAPACITĂȚI (VERSIUNILE 1-6)
# ==========================================

# Lungimea totală a șirului de biți pentru fiecare versiune
QR_BIT_LENGTHS = [208, 352, 560, 800, 1072, 1376]

# Dimensiunea laturii matricei (ex: Versiunea 1 este 21x21, Versiunea 2 este 25x25)
QR_MATRIX_SIZES = [21, 25, 29, 33, 37, 41]

# Configurația de decodare și Error Correction (Nivel: HIGH)
# Format -> Versiune: (Capacitate_Biți_Date, Total_Bytes_Cu_ECC)
QR_CONFIG_HIGH = {
    1: (72, 26),
    2: (128, 44),
    3: (208, 70),
    4: (288, 100),
    5: (368, 134),
    6: (480, 172),
}

# ==========================================
# 2. DATE PROTOCOL ȘI PADDING
# ==========================================

# Indicatorul pentru nivelul de corecție a erorilor 'High' (2 biți)
ECC_LEVEL_HIGH = "10"

# Biții de padding standard folosiți pentru umplerea spațiului rămas (0xEC și 0x11)
PADDING_BYTES = ("11101100", "00010001")

# ==========================================
# 3. ZONE REZERVATE (STRUCTURĂ GEOMETRICĂ)
# ==========================================

# Coordonatele (x, y) pentru centrul Alignment Patterns (Versiunile 2-6)
# Versiunea 1 nu are Alignment Pattern.
ALIGNMENT_PATTERN_COORDS = {
    2: [(18, 18)],
    3: [(22, 22)],
    4: [(26, 26)],
    5: [(30, 30)],
    6: [(34, 34)]
}

# ==========================================
# 4. CONSTANTE MATEMATICE (FORMAT INFORMATION)
# ==========================================

# Polinomul generator pentru codul BCH (15, 5)
# Formula matematică: x^10 + x^8 + x^5 + x^4 + x^2 + x + 1
BCH_POLYNOMIAL = 0b10100110111

# Masca XOR standard aplicată peste șirul final de 15 biți al formatului
FORMAT_XOR_MASK = 0b101010000010010