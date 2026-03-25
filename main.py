import sys
from encoder import scriere_cod_qr
from decoder import citire_cod_qr

def afiseaza_meniu():
    print("\n" + "="*25)
    print("SCAN GOGH - MAIN MENU")
    print("="*25)
    print("1) Generare cod QR")
    print("2) Citire cod QR")
    print("3) Ieșire")
    print("-" * 25)

def main():
    while True:
        afiseaza_meniu()
        optiune = input("Alege o opțiune: ").strip()

        if optiune == "1":
            scriere_cod_qr()
        elif optiune == "2":
            citire_cod_qr()
        elif optiune == "3":
            print("\nLa revedere! Vă mulțumim că ați folosit Scan Gogh.")
            sys.exit(0)
        else:
            print("\nEroare: Opțiune invalidă. Te rugăm să încerci din nou.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProgram întrerupt de utilizator. Ieșire...")
        sys.exit(0)