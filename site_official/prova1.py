import sys

def main():
    # Controlla se è stato passato un argomento (il campo)
    if len(sys.argv) > 1:
        campo = sys.argv[1]
        print(f"Campo selezionato: {campo}")
        # Fai le operazioni necessarie con il parametro campo
    else:
        print("Nessun campo specificato")
    
    print("sono connesso")

if __name__ == "__main__":
    main()