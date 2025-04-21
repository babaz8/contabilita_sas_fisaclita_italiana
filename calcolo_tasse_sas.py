#!/usr/bin/env python3
import argparse
import sys
import sqlite3
import os.path
import datetime
from typing import Dict, Tuple, List, Optional, Any

# Aliquote IRPEF (esempio 2025)
IRPEF_BRACKETS = [
    (15000, 0.23),
    (28000, 0.25),
    (50000, 0.35),
    (float('inf'), 0.43)
]

# Database setup
DB_FILE = "sas_settings.db"

def init_database():
    """Initialize the database if it doesn't exist"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create company profiles table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create partners table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS partners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        percentage REAL NOT NULL,
        role TEXT NOT NULL,
        FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE,
        UNIQUE(company_id, name)
    )
    ''')
    
    # Create calculations history table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS calculations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        company_id INTEGER NOT NULL,
        sales_gross REAL NOT NULL,
        input_vat REAL NOT NULL,
        vat_rate REAL NOT NULL,
        expenses REAL NOT NULL,
        calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE
    )
    ''')
    
    # Create calculation results table for detailed results
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS calculation_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        calculation_id INTEGER NOT NULL,
        partner_id INTEGER NOT NULL,
        share REAL NOT NULL,
        irpef REAL NOT NULL,
        inps REAL NOT NULL,
        net_income REAL NOT NULL,
        FOREIGN KEY (calculation_id) REFERENCES calculations (id) ON DELETE CASCADE,
        FOREIGN KEY (partner_id) REFERENCES partners (id) ON DELETE CASCADE
    )
    ''')
    
    conn.commit()
    conn.close()

def save_company(name: str, partners: Dict[str, float], roles: Dict[str, str]) -> int:
    """Save company profile to database"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if company already exists
        cursor.execute('SELECT id FROM companies WHERE name = ?', (name,))
        existing = cursor.fetchone()
        if existing:
            print(f"La società '{name}' esiste già. Verrà aggiornata.")
            company_id = existing[0]
            # Delete existing partners
            cursor.execute('DELETE FROM partners WHERE company_id = ?', (company_id,))
        else:
            # Insert new company
            cursor.execute('INSERT INTO companies (name) VALUES (?)', (name,))
            company_id = cursor.lastrowid
        
        # Insert partners
        for partner_name, percentage in partners.items():
            role = roles[partner_name]
            cursor.execute('''
            INSERT INTO partners (company_id, name, percentage, role)
            VALUES (?, ?, ?, ?)
            ''', (company_id, partner_name, percentage, role))
        
        conn.commit()
        conn.close()
        return company_id
    except sqlite3.Error as e:
        print(f"Errore nel salvare la società: {e}")
        return -1

def save_calculation(name: str, company_id: int, sales_gross: float, input_vat: float, 
                    vat_rate: float, expenses: float, results: List[Dict[str, Any]]) -> bool:
    """Save calculation to history"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Insert calculation
        cursor.execute('''
        INSERT INTO calculations (name, company_id, sales_gross, input_vat, vat_rate, expenses)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, company_id, sales_gross, input_vat, vat_rate, expenses))
        
        calculation_id = cursor.lastrowid
        
        # Insert results
        for result in results:
            cursor.execute('''
            INSERT INTO calculation_results 
            (calculation_id, partner_id, share, irpef, inps, net_income)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (calculation_id, result['partner_id'], result['share'], 
                 result['irpef'], result['inps'], result['net_income']))
        
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Errore nel salvare il calcolo: {e}")
        return False

def list_companies() -> List[Tuple[int, str]]:
    """List all saved companies"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM companies ORDER BY name')
        companies = cursor.fetchall()
        conn.close()
        return companies
    except sqlite3.Error as e:
        print(f"Errore nel recuperare le società: {e}")
        return []

def list_calculations() -> List[Tuple[int, str, str, str]]:
    """List all saved calculations with company name and date"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
        SELECT c.id, c.name, co.name, c.calculation_date 
        FROM calculations c
        JOIN companies co ON c.company_id = co.id
        ORDER BY c.calculation_date DESC
        ''')
        calculations = cursor.fetchall()
        conn.close()
        return calculations
    except sqlite3.Error as e:
        print(f"Errore nel recuperare lo storico calcoli: {e}")
        return []

def load_company(company_id: int) -> Optional[Tuple]:
    """Load a company profile by ID"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get company details
        cursor.execute('SELECT id, name FROM companies WHERE id = ?', (company_id,))
        company_data = cursor.fetchone()
        if not company_data:
            conn.close()
            return None
        
        # Get partners for this company
        cursor.execute('''
        SELECT id, name, percentage, role FROM partners WHERE company_id = ?
        ''', (company_id,))
        
        partners_data = cursor.fetchall()
        conn.close()
        
        # Format data
        company_id, company_name = company_data
        partner_ids = {p[1]: p[0] for p in partners_data}  # name -> id
        partners = {p[1]: p[2] for p in partners_data}     # name -> percentage
        roles = {p[1]: p[3] for p in partners_data}        # name -> role
        
        return company_id, company_name, partner_ids, partners, roles
    except sqlite3.Error as e:
        print(f"Errore nel caricare la società: {e}")
        return None

def load_calculation(calc_id: int) -> Optional[Dict]:
    """Load a calculation by ID"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get calculation details
        cursor.execute('''
        SELECT c.id, c.name, c.company_id, c.sales_gross, c.input_vat, c.vat_rate, c.expenses,
               co.name AS company_name
        FROM calculations c
        JOIN companies co ON c.company_id = co.id
        WHERE c.id = ?
        ''', (calc_id,))
        
        calc_data = cursor.fetchone()
        if not calc_data:
            conn.close()
            return None
        
        # Get company and partners
        company_id = calc_data[2]
        company_data = load_company(company_id)
        if not company_data:
            conn.close()
            return None
        
        _, company_name, partner_ids, partners, roles = company_data
        
        # Get calculation results
        cursor.execute('''
        SELECT cr.partner_id, p.name, cr.share, cr.irpef, cr.inps, cr.net_income
        FROM calculation_results cr
        JOIN partners p ON cr.partner_id = p.id
        WHERE cr.calculation_id = ?
        ''', (calc_id,))
        
        results_data = cursor.fetchall()
        conn.close()
        
        # Format data
        calc_id, calc_name, _, sales_gross, input_vat, vat_rate, expenses, _ = calc_data
        results = []
        for partner_id, partner_name, share, irpef, inps, net_income in results_data:
            results.append({
                'partner_id': partner_id,
                'partner_name': partner_name,
                'share': share,
                'irpef': irpef,
                'inps': inps,
                'net_income': net_income
            })
        
        return {
            'id': calc_id,
            'name': calc_name,
            'company_id': company_id,
            'company_name': company_name,
            'sales_gross': sales_gross,
            'input_vat': input_vat,
            'vat_rate': vat_rate,
            'expenses': expenses,
            'partners': partners,
            'roles': roles,
            'results': results
        }
    except sqlite3.Error as e:
        print(f"Errore nel caricare il calcolo: {e}")
        return None

def delete_company(company_id: int) -> bool:
    """Delete a company by ID"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM companies WHERE id = ?', (company_id,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Errore nell'eliminare la società: {e}")
        return False

def delete_calculation(calc_id: int) -> bool:
    """Delete a calculation by ID"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM calculations WHERE id = ?', (calc_id,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Errore nell'eliminare il calcolo: {e}")
        return False

# Funzione calcolo contributi INPS per socio accomandatario
def calculate_inps_accomandatario(net_profit: float) -> float:
    """Calcola contributi INPS per il socio accomandatario"""
    INPS_MIN_CONTRIBUTION = 4300    # importo fisso annuo
    INPS_RATE = 0.24                # aliquota su eccedenza
    INPS_THRESHOLD = 18415          # soglia contributiva
    if net_profit <= 0:
        return 0.0
    contribution = INPS_MIN_CONTRIBUTION
    if net_profit > INPS_THRESHOLD:
        contribution += (net_profit - INPS_THRESHOLD) * INPS_RATE
    return contribution

# Calcoli IVA
def calculate_vat(sales_gross: float, input_vat: float, vat_rate: float) -> dict:
    sales_net = sales_gross / (1 + vat_rate)
    vat_output = sales_gross - sales_net
    vat_due = vat_output - input_vat
    return {'sales_net': sales_net, 'vat_output': vat_output, 'vat_input': input_vat, 'vat_due': vat_due}

# Calcolo utile netto
def calculate_net_profit(sales_net: float, expenses: float) -> float:
    return sales_net - expenses

# Calcolo IRPEF progressiva
def calculate_irpef(income: float) -> float:
    tax = 0.0
    lower = 0.0
    remaining = income
    for upper, rate in IRPEF_BRACKETS:
        if remaining <= 0:
            break
        taxable = min(upper - lower, remaining)
        tax += taxable * rate
        remaining -= taxable
        lower = upper
    return tax

# Parsing socio CLI
def parse_partner(arg: str):
    try:
        parts = arg.split(":")
        if len(parts) != 3:
            raise ValueError("Format must be name:quota:role")
        name, pct_str, role = parts
        pct = float(pct_str)
        role = role.lower()
        if role not in ('accomandante', 'accomandatario'):
            raise ValueError("Role must be 'accomandante' or 'accomandatario'")
        return name, pct, role
    except Exception as e:
        raise argparse.ArgumentTypeError(
            f"Partner deve essere nel formato name:quota:role con ruolo 'accomandante' o 'accomandatario'. Error: {str(e)}"
        )

def get_float_input(prompt):
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("Errore: inserisci un numero valido.")

def get_int_input(prompt):
    while True:
        try:
            value = int(input(prompt))
            return value
        except ValueError:
            print("Errore: inserisci un numero intero valido.")

def get_yes_no_input(prompt):
    while True:
        response = input(prompt).lower()
        if response in ('s', 'si', 'sì', 'y', 'yes'):
            return True
        elif response in ('n', 'no'):
            return False
        print("Errore: rispondi con 's' o 'n'.")

def get_valid_name(prompt):
    while True:
        name = input(prompt).strip()
        if name:
            return name
        print("Errore: il nome non può essere vuoto.")

# Menu iniziale
def show_main_menu():
    print("\n===== Calcolo Tassazione S.a.s. =====")
    print("1. Inizia un nuovo calcolo")
    print("2. Gestisci società")
    print("3. Storico calcoli effettuati")
    print("0. Esci")
    
    choice = get_int_input("Seleziona un'opzione: ")
    return choice

def company_selection_menu():
    """Menu per selezionare una società esistente o crearne una nuova"""
    print("\n===== Selezione Società =====")
    print("1. Usa una società esistente")
    print("2. Crea una nuova società")
    print("0. Torna al menu principale")
    
    choice = get_int_input("Seleziona un'opzione: ")
    
    if choice == 0:
        return None
    elif choice == 1:
        return select_existing_company()
    elif choice == 2:
        return create_new_company()
    else:
        print("Scelta non valida.")
        return None

def select_existing_company():
    """Menu per selezionare una società esistente"""
    print("\n===== Società Esistenti =====")
    companies = list_companies()
    
    if not companies:
        print("Nessuna società salvata.")
        return None
        
    print("Società disponibili:")
    for i, (company_id, name) in enumerate(companies, 1):
        print(f"{i}. {name}")
    
    print("\n0. Torna indietro")
    
    choice = get_int_input("Seleziona una società (0 per tornare): ")
    if choice == 0:
        return None
        
    if 1 <= choice <= len(companies):
        return load_company(companies[choice-1][0])
    else:
        print("Scelta non valida.")
        return None

def create_new_company():
    """Crea una nuova società"""
    print("\n===== Creazione Nuova Società =====")
    
    company_name = get_valid_name("Nome società: ")
    n = get_int_input("Numero di soci: ")
    
    partners = {}
    roles = {}
    total_pct = 0
    
    for i in range(1, n+1):
        name = get_valid_name(f"Nome socio #{i}: ")
        pct = get_float_input(f"Quota percentuale socio '{name}' (es. 80): ")
        total_pct += pct
        
        while True:
            role = input(f"Ruolo socio '{name}' ('accomandante' o 'accomandatario'): ").lower()
            if role in ('accomandante', 'accomandatario'):
                break
            print("Errore: ruolo non valido. Usa 'accomandante' o 'accomandatario'.")
            
        partners[name] = pct
        roles[name] = role
    
    # Verifica che le quote totali siano circa 100%
    if not (99.0 <= total_pct <= 101.0):
        print(f"Attenzione: la somma delle quote ({total_pct}%) non è pari al 100%")
        if get_yes_no_input("Continuare comunque? (s/n): "):
            # Normalizzazione opzionale delle quote
            if get_yes_no_input("Normalizzare le quote al 100%? (s/n): "):
                factor = 100.0 / total_pct
                partners = {name: pct * factor for name, pct in partners.items()}
                print("Quote normalizzate al 100%")
        else:
            print("Operazione annullata.")
            return None
    
    # Verifica che ci sia almeno un socio accomandatario
    if 'accomandatario' not in roles.values():
        print("Errore: deve esserci almeno un socio accomandatario in una S.a.s.")
        return None
    
    company_id = save_company(company_name, partners, roles)
    if company_id > 0:
        print(f"Società '{company_name}' salvata con successo.")
        return load_company(company_id)
    else:
        print("Errore nel salvare la società.")
        return None

def manage_companies_menu():
    """Menu per gestire le società"""
    while True:
        print("\n===== Gestione Società =====")
        companies = list_companies()
        
        if not companies:
            print("Nessuna società salvata.")
            input("Premi INVIO per tornare al menu principale.")
            return
            
        print("Società disponibili:")
        for i, (company_id, name) in enumerate(companies, 1):
            print(f"{i}. {name}")
        
        print("\n0. Torna al menu principale")
        
        choice = get_int_input("Seleziona una società (0 per tornare): ")
        if choice == 0:
            return
            
        if 1 <= choice <= len(companies):
            company_id = companies[choice-1][0]
            company_data = load_company(company_id)
            
            if not company_data:
                print("Errore nel caricare i dati della società.")
                continue
            
            _, company_name, _, partners, roles = company_data
            
            print(f"\n===== Dettagli Società: {company_name} =====")
            print("Soci:")
            for name, pct in partners.items():
                role = roles[name]
                print(f"  - {name}: {pct}% ({role})")
            
            print("\n1. Modifica società")
            print("2. Elimina società")
            print("0. Torna al menu precedente")
            
            sub_choice = get_int_input("Seleziona un'opzione: ")
            
            if sub_choice == 0:
                continue
            elif sub_choice == 1:
                # Ricreare la società (sovrascrive quella esistente)
                new_company = create_new_company()
                if new_company:
                    print("Società aggiornata con successo.")
            elif sub_choice == 2:
                if get_yes_no_input(f"Sei sicuro di voler eliminare la società '{company_name}'? (s/n): "):
                    if delete_company(company_id):
                        print("Società eliminata con successo.")
                    else:
                        print("Errore nell'eliminazione della società.")
            else:
                print("Scelta non valida.")
        else:
            print("Scelta non valida.")

def calculation_history_menu():
    """Menu per visualizzare lo storico dei calcoli"""
    while True:
        print("\n===== Storico Calcoli Effettuati =====")
        calculations = list_calculations()
        
        if not calculations:
            print("Nessun calcolo salvato.")
            input("Premi INVIO per tornare al menu principale.")
            return
            
        print("Calcoli disponibili:")
        for i, (calc_id, calc_name, company_name, date) in enumerate(calculations, 1):
            # Format date nicely
            try:
                date_obj = datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
                formatted_date = date_obj.strftime("%d/%m/%Y %H:%M")
            except:
                formatted_date = date  # Use as is if format is unexpected
            print(f"{i}. [{formatted_date}] {calc_name} - {company_name}")
        
        print("\n0. Torna al menu principale")
        
        choice = get_int_input("Seleziona un calcolo (0 per tornare): ")
        if choice == 0:
            return
            
        if 1 <= choice <= len(calculations):
            calc_id = calculations[choice-1][0]
            calc_data = load_calculation(calc_id)
            
            if not calc_data:
                print("Errore nel caricare i dati del calcolo.")
                continue
            
            print(f"\n===== Dettagli Calcolo: {calc_data['name']} =====")
            print(f"Società: {calc_data['company_name']}")
            print(f"Ricavi lordi (inclusa IVA): {calc_data['sales_gross']:.2f} €")
            print(f"IVA pagata sugli acquisti: {calc_data['input_vat']:.2f} €")
            print(f"Aliquota IVA vendite: {calc_data['vat_rate']:.2f}")
            print(f"Spese nette totali: {calc_data['expenses']:.2f} €")
            
            print("\nRisultati:")
            for result in calc_data['results']:
                print(f"  Socio: {result['partner_name']}")
                print(f"    Quota utile: {result['share']:.2f} €")
                print(f"    IRPEF dovuta: {result['irpef']:.2f} €")
                print(f"    INPS dovuta: {result['inps']:.2f} €")
                print(f"    Netto dopo tasse: {result['net_income']:.2f} €")
            
            print("\n1. Ripeti questo calcolo")
            print("2. Elimina questo calcolo")
            print("0. Torna al menu precedente")
            
            sub_choice = get_int_input("Seleziona un'opzione: ")
            
            if sub_choice == 0:
                continue
            elif sub_choice == 1:
                # Ripeti il calcolo con gli stessi parametri
                company_data = load_company(calc_data['company_id'])
                if company_data:
                    _, _, partner_ids, partners, roles = company_data
                    run_calculation_flow(calc_data['sales_gross'], calc_data['input_vat'], 
                                        calc_data['vat_rate'], calc_data['expenses'],
                                        calc_data['company_id'], partner_ids, partners, roles)
            elif sub_choice == 2:
                if get_yes_no_input(f"Sei sicuro di voler eliminare questo calcolo? (s/n): "):
                    if delete_calculation(calc_id):
                        print("Calcolo eliminato con successo.")
                    else:
                        print("Errore nell'eliminazione del calcolo.")
            else:
                print("Scelta non valida.")
        else:
            print("Scelta non valida.")

def new_calculation_flow():
    """Flusso per un nuovo calcolo"""
    # Seleziona/crea società
    company_data = company_selection_menu()
    if not company_data:
        return
    
    company_id, company_name, partner_ids, partners, roles = company_data
    
    # Richiedi dati finanziari
    print(f"\n===== Nuovo Calcolo per {company_name} =====")
    sales_gross = get_float_input("Ricavi lordi (inclusa IVA) €: ")
    input_vat = get_float_input("IVA pagata sugli acquisti €: ")
    vat_rate = get_float_input("Aliquota IVA vendite (es. 0.22): ")
    expenses = get_float_input("Spese nette totali (senza IVA) €: ")
    
    # Esegui calcolo
    run_calculation_flow(sales_gross, input_vat, vat_rate, expenses, 
                        company_id, partner_ids, partners, roles)

def run_calculation_flow(sales_gross, input_vat, vat_rate, expenses, 
                         company_id, partner_ids, partners, roles):
    """Esegue il calcolo e salva i risultati"""
    # Calcoli finanziari
    vat_res = calculate_vat(sales_gross, input_vat, vat_rate)
    profit = calculate_net_profit(vat_res['sales_net'], expenses)
    allocation = {name: profit * pct / 100 for name, pct in partners.items()}

    # Preparazione risultati per visualizzazione e salvataggio
    calculation_results = []
    total_irpef = 0.0
    total_inps = 0.0
    final_profit = profit
    
    for name, share in allocation.items():
        irpef = calculate_irpef(share)
        inps = calculate_inps_accomandatario(share) if roles[name] == 'accomandatario' else 0.0
        net_income = share - irpef - inps
        total_irpef += irpef
        total_inps += inps
        final_profit -= (irpef + inps)
        
        # Aggiungi risultato ai risultati del calcolo
        calculation_results.append({
            'partner_id': partner_ids[name],
            'partner_name': name,
            'share': share,
            'irpef': irpef,
            'inps': inps,
            'net_income': net_income
        })

    # Visualizza risultati
    print("\n--- Risultati Calcolo S.a.s. ---")
    print(f"Ricavi netti (senza IVA): {vat_res['sales_net']:.2f} €")
    print(f"IVA a debito: {vat_res['vat_output']:.2f} €")
    print(f"IVA a credito: {vat_res['vat_input']:.2f} €")
    print(f"IVA dovuta: {vat_res['vat_due']:.2f} €\n")
    print(f"Utile netto ante imposte e contributi: {profit:.2f} €\n")
    
    for result in calculation_results:
        print(f"Socio: {result['partner_name']}")
        print(f"  Quota utile: {result['share']:.2f} €")
        print(f"  IRPEF dovuta: {result['irpef']:.2f} €")
        print(f"  INPS dovuta: {result['inps']:.2f} €")
        print(f"  Netto dopo tasse: {result['net_income']:.2f} €\n")

    print(f"Totale IRPEF: {total_irpef:.2f} €")
    print(f"Totale INPS: {total_inps:.2f} €")
    print(f"Utile netto finale dopo imposte e contributi: {final_profit:.2f} €")
    print(f"Percentuale di tassazione effettiva: {((total_irpef + total_inps) / profit * 100) if profit > 0 else 0:.2f}%")
    
    # Chiedi se salvare il calcolo
    if get_yes_no_input("\nVuoi salvare questo calcolo nello storico? (s/n): "):
        calc_name = get_valid_name("Nome per questo calcolo: ")
        if save_calculation(calc_name, company_id, sales_gross, input_vat, 
                           vat_rate, expenses, calculation_results):
            print(f"Calcolo '{calc_name}' salvato con successo nello storico.")
        else:
            print("Errore nel salvare il calcolo nello storico.")
    
    input("\nPremi INVIO per continuare.")

# Funzione principale
def main():
    # Inizializza il database
    init_database()
    
    # Parametri CLI
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(
            description='Calcolo tassazione S.a.s. (IRPEF, INPS, IVA) via CLI o interattivo')
        parser.add_argument('--sales-gross', type=float, help='Ricavi lordi (inclusa IVA)')
        parser.add_argument('--input-vat', type=float, help='IVA pagata sugli acquisti detraibile')
        parser.add_argument('--vat-rate', type=float, default=0.22, help='Aliquota IVA vendite')
        parser.add_argument('--expenses', type=float, help='Spese nette totali (senza IVA)')
        parser.add_argument('--partner', type=parse_partner, action='append', dest='partners',
                           help='Partner name:quota:role')
        args = parser.parse_args()

        # Verifica parametri CLI
        if not all([args.sales_gross is not None, args.input_vat is not None, 
                  args.expenses is not None, args.partners]):
            parser.print_help()
            sys.exit(1)

        sales_gross = args.sales_gross
        input_vat = args.input_vat
        vat_rate = args.vat_rate
        expenses = args.expenses
        
        # Estrae i dati dei partner
        partners = {name: pct for name, pct, _ in args.partners}
        roles = {name: role for name, _, role in args.partners}
        
        # Crea una società temporanea per il calcolo CLI
        company_name = "Società Temporanea CLI"
        company_id = save_company(company_name, partners, roles)
        
        if company_id > 0:
            company_data = load_company(company_id)
            if company_data:
                _, _, partner_ids, partners, roles = company_data
                # Esegui calcolo senza salvare nello storico
                vat_res = calculate_vat(sales_gross, input_vat, vat_rate)
                profit = calculate_net_profit(vat_res['sales_net'], expenses)
                allocation = {name: profit * pct / 100 for name, pct in partners.items()}
                
                # Output risultati
                print("\n--- Risultati Calcolo S.a.s. ---")
                print(f"Ricavi netti (senza IVA): {vat_res['sales_net']:.2f} €")
                print(f"IVA a debito: {vat_res['vat_output']:.2f} €")
                print(f"IVA a credito: {vat_res['vat_input']:.2f} €")
                print(f"IVA dovuta: {vat_res['vat_due']:.2f} €\n")
                print(f"Utile netto ante imposte e contributi: {profit:.2f} €\n")
                
                total_irpef = 0.0
                total_inps = 0.0
                final_profit = profit
                
                for name, share in allocation.items():
                    irpef = calculate_irpef(share)
                    inps = calculate_inps_accomandatario(share) if roles[name] == 'accomandatario' else 0.0
                    total_irpef += irpef
                    total_inps += inps
                    final_profit -= (irpef + inps)
                    
                    print(f"Socio: {name}")
                    print(f"  Quota utile: {share:.2f} €")
                    print(f"  IRPEF dovuta: {irpef:.2f} €")
                    print(f"  INPS dovuta: {inps:.2f} €")
                    print(f"  Netto dopo tasse: {share - irpef - inps:.2f} €\n")
                
                print(f"Totale IRPEF: {total_irpef:.2f} €")
                print(f"Totale INPS: {total_inps:.2f} €")
                print(f"Utile netto finale dopo imposte e contributi: {final_profit:.2f} €")
                print(f"Percentuale di tassazione effettiva: {((total_irpef + total_inps) / profit * 100) if profit > 0 else 0:.2f}%")
                
                # Elimina la società temporanea
                delete_company(company_id)
        sys.exit(0)
    
    # Modalità interattiva con menu
    while True:
        choice = show_main_menu()
        
        if choice == 0:
            print("Grazie per aver utilizzato il calcolatore S.a.s. Arrivederci!")
            sys.exit(0)
            
        elif choice == 1:
            # Nuovo calcolo
            new_calculation_flow()
                
        elif choice == 2:
            # Gestisci società
            manage_companies_menu()
                
        elif choice == 3:
            # Storico calcoli
            calculation_history_menu()
                
        else:
            print("Opzione non valida.")

if __name__ == '__main__':
    main()