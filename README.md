# 💼 Calcolatore Tassazione S.a.s.

Un'applicazione Python per il calcolo interattivo e/o da riga di comando della tassazione per società in accomandita semplice (S.a.s.), comprensiva di:

- Calcolo IRPEF per soci
- Contributi INPS per accomandatari
- IVA (calcolo debito/credito)
- Gestione di soci, ruoli e percentuali
- Storico dei calcoli effettuati

## 📦 Funzionalità principali

- Modalità interattiva con menu testuale
- Salvataggio dei profili società e soci in database SQLite
- Storico dei calcoli consultabile e ripetibile
- Supporto a soci con ruoli di `accomandante` o `accomandatario`
- Supporto CLI per utilizzo in script/automatismi

## 🚀 Requisiti

- Python 3.7+
- Nessuna dipendenza esterna (solo standard library)

## 🛠️ Installazione

1. Clona il repository:

```bash
git clone https://github.com/tuo-utente/calcolatore-sas.git
cd calcolatore-sas
```

2. Rendi eseguibile lo script:

```bash
chmod +x calcolatore_sas.py
```

3. Esegui il programma:

```bash
./calcolatore_sas.py
```

Oppure:

```bash
python3 calcolatore_sas.py
```

## 📈 Esempio di utilizzo (interattivo)

```bash
$ python3 calcolatore_sas.py
```

Ti guiderà passo-passo nella:

- Creazione o selezione di una società
- Inserimento dati economici (ricavi, IVA, spese)
- Calcolo e salvataggio dei risultati

## ⚙️ Utilizzo da CLI

Puoi anche eseguire un calcolo direttamente da terminale:

```bash
python3 calcolatore_sas.py \
  --sales-gross 30000 \
  --input-vat 2000 \
  --vat-rate 0.22 \
  --expenses 10000 \
  --partner "Mario Rossi:70:accomandatario" \
  --partner "Luigi Bianchi:30:accomandante"
```

📌 Nota: in modalità CLI i dati non vengono salvati nello storico.

## 🧮 Tassazione calcolata

- **IRPEF** secondo le aliquote progressive in vigore (2025)
- **INPS** per soci accomandatari con soglia e aliquota configurata
- **IVA** calcolo IVA a debito, credito e saldo
- **Ripartizione utile** netta tra soci in base alle percentuali

## 🗃️ Database

Tutti i dati vengono salvati in un file SQLite locale (`sas_settings.db`) nella stessa directory del programma.

## 🔐 Licenza

MIT License. Vedi `LICENSE` per maggiori dettagli.

## 🙌 Contributi

Pull request e suggerimenti benvenuti! Questo tool è pensato per piccoli studi commerciali, professionisti o chi gestisce piccole S.a.s.
