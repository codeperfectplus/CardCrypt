import json
import os
import getpass
import time
from pathlib import Path
from cryptography.fernet import Fernet
from colorama import init, Fore, Style
from tabulate import tabulate

init(autoreset=True)

ROOT_DIR = Path(__file__).resolve(strict=True).parent
SECRETS_DIR = ROOT_DIR / "secrets"
DATA_DIR = ROOT_DIR / "data"

os.makedirs(SECRETS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

class SecureStorage:
    KEY_FILE = "secrets/secret.key"
    PIN_FILE = "secrets/pin.enc"
    DATA_FILE = "data/cards.enc"
    SESSION = {"pin_verified_at": None}
   


    @classmethod
    def load_key(cls):
        with open(cls.KEY_FILE, "rb") as f:
            return f.read()

    @classmethod
    def ensure_key_exists(cls):
        if not os.path.exists(cls.KEY_FILE):
            os.makedirs(os.path.dirname(cls.KEY_FILE), exist_ok=True)
            key = Fernet.generate_key()
            with open(cls.KEY_FILE, "wb") as f:
                f.write(key)
            print(Fore.YELLOW + "Encryption key generated and saved.")


    @classmethod
    def encrypt(cls, data):
        return Fernet(cls.load_key()).encrypt(json.dumps(data).encode())

    @classmethod
    def decrypt(cls, encrypted_data):
        return json.loads(Fernet(cls.load_key()).decrypt(encrypted_data).decode())

    @classmethod
    def create_pin(cls):
        pin = ""
        while not (pin.isdigit() and len(pin) == 6):
            pin = getpass.getpass(Fore.CYAN + "Set a 6-digit PIN for viewing cards: ")
        encrypted_pin = Fernet(cls.load_key()).encrypt(pin.encode())
        with open(cls.PIN_FILE, "wb") as f:
            f.write(encrypted_pin)
        print(Fore.GREEN + "PIN saved securely.")

    @classmethod
    def verify_pin(cls):
        now = time.time()
        if cls.SESSION["pin_verified_at"] and (now - cls.SESSION["pin_verified_at"] < 300):
            return True

        if not os.path.exists(cls.PIN_FILE):
            print(Fore.RED + "PIN not found. Please set it up again.")
            cls.create_pin()
            cls.SESSION["pin_verified_at"] = now
            return True

        fernet = Fernet(cls.load_key())
        with open(cls.PIN_FILE, "rb") as f:
            stored_encrypted_pin = f.read()

        stored_pin = fernet.decrypt(stored_encrypted_pin).decode()
        attempts = 3
        while attempts > 0:
            pin = getpass.getpass(Fore.CYAN + "Enter your 6-digit PIN to view details: ")
            if pin == stored_pin:
                cls.SESSION["pin_verified_at"] = now
                return True
            else:
                attempts -= 1
                print(Fore.RED + f"Incorrect PIN. {attempts} attempts left.")
        print(Fore.RED + "Too many incorrect attempts. Access denied.")
        return False


class CardManager:
    @staticmethod
    def load_all_cards():
        if not os.path.exists(SecureStorage.DATA_FILE):
            return []
        with open(SecureStorage.DATA_FILE, "rb") as f:
            card_data = SecureStorage.decrypt(f.read())
            card_data.sort(key=lambda x: x.get("Bank Name", "").lower())
            return card_data

    @staticmethod
    def save_all_cards(cards):
        with open(SecureStorage.DATA_FILE, "wb") as f:
            f.write(SecureStorage.encrypt(cards))

    @staticmethod
    def save_card(card_info):
        cards = CardManager.load_all_cards()
        if any(card.get("Card Number") == card_info.get("Card Number") for card in cards):
            print(Fore.YELLOW + "Card with this number already exists. Not saving duplicate.")
            return
        cards.append(card_info)
        CardManager.save_all_cards(cards)
        print(Fore.GREEN + "Card saved successfully.")

    @staticmethod
    def delete_card(index):
        cards = CardManager.load_all_cards()
        if 0 <= index < len(cards):
            del cards[index]
            CardManager.save_all_cards(cards)
            print(Fore.GREEN + "Card deleted successfully.")

    @staticmethod
    def update_card(index, updated_card):
        cards = CardManager.load_all_cards()
        if 0 <= index < len(cards):
            cards[index] = updated_card
            CardManager.save_all_cards(cards)
            print(Fore.GREEN + "Card updated successfully.")


class CardCLI:
    @staticmethod
    def add_card():
        print(Fore.CYAN + "\n--- Add New Credit Card ---")
        name = input("Card Name: ")
        holder = "Deepak Raj"
        number = input("Card Number: ")
        expiry = input("Expiry Date (MM/YY): ")
        cvv = input("CVV: ")
        want_to_add_more = input("Do you want to add more info (y/n): ").strip().lower()

        card = {
            "Card Name": name,
            "Card Holder": holder,
            "Card Number": number,
            "Expiry Date": expiry,
            "CVV": cvv,
            "Card Type": "Visa" if number.startswith("4") else "MasterCard" if number.startswith("5") else "RuPay" if number.startswith("6") else "Unknown",
            "Created At": time.strftime("%Y-%m-%d %H:%M:%S"),
            "Bank Name": "",
            "Lounge Access": "",
            "Forex Markup": "",
            "Special Benefit": "",
            "Joining Fee": "",
            "Annual Charges": "",
            "Paid or LTF": "",
            "Need to Close": ""
        }

        if want_to_add_more == 'y':
            for field in ["Bank Name", "Lounge Access", "Forex Markup", "Special Benefit", "Joining Fee", "Annual Charges", "Paid or LTF", "Need to Close"]:
                card[field] = input(f"{field}: ")

        CardManager.save_card(card)

    @staticmethod
    def add_spend():
        cards = CardManager.load_all_cards()
        if not cards:
            print(Fore.YELLOW + "No cards available.")
            return

        for idx, card in enumerate(cards, 1):
            print(f"{idx}. {card['Card Name']}")

        choice = input("Select card to add spend (or 'q' to cancel): ")
        if choice.lower() == 'q':
            return
        index = int(choice) - 1

        if not SecureStorage.verify_pin():
            return

        spend_name = input("Spend Name: ")
        amount = input("Amount (₹): ")
        spend_entry = {
            "Name": spend_name,
            "Amount": amount,
            "Date": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        cards[index].setdefault("Spends", []).append(spend_entry)
        CardManager.update_card(index, cards[index])


    @staticmethod
    def list_and_view():
        cards = CardManager.load_all_cards()
        if not cards:
            print(Fore.YELLOW + "No cards found.")
            return

        headers = ["No.", "Card Name", "Card Type", "Masked Number", "Bank Name", "Joining Fee", "Annual Charges", "Need to Close"]
        table = []
        for idx, card in enumerate(cards, 1):
            masked_number = card.get("Card Number", "")[:2] + "*" * (len(card.get("Card Number", "")) - 6) + card.get("Card Number", "")[-2:]
            row = [idx, card['Card Name'], card['Card Type'], masked_number, card.get('Bank Name', ''), card.get('Joining Fee', ''), card.get('Annual Charges', ''), card.get('Need to Close', '')]
            table.append(row)

        print(Fore.GREEN + tabulate(table, headers, tablefmt="fancy_grid"))

        choice = input(Fore.CYAN + "\nEnter the number of the card to view details (or 'q' to cancel): ")
        if choice.lower() == 'q':
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(cards)):
            print(Fore.RED + "Invalid choice.")
            return

        if SecureStorage.verify_pin():
            card = cards[int(choice) - 1]
            print(Fore.GREEN + "\n--- Card Details ---")
            CardCLI.print_card_details_fancy(card)
    

    def print_card_details_fancy(card):
        def format_line(icon, label, value, width=60):
            text = f"{icon}  {label:<15}: {value}"
            return f"║ {text:<{width}} ║"

        def format_bullet_line(text, width=60):
            return f"║ • {text:<{width - 4}} ║"

        width = 60
        print(Fore.GREEN + f"╔{'═' * width}╗")
        print(Fore.GREEN + f"║{'💳 Credit Card Details':^{width}}║")
        print(Fore.GREEN + f"╠{'═' * width}╣")

        print(Fore.GREEN + format_line("🏷️", "Card Name", card.get("Card Name", "")))
        print(Fore.GREEN + format_line("👤", "Card Holder", card.get("Card Holder", "")))
        print(Fore.GREEN + format_line("🔢", "Card Number", card.get("Card Number", "")))
        print(Fore.GREEN + format_line("💳", "Card Type", card.get("Card Type", "")))
        print(Fore.GREEN + format_line("📅", "Expiry Date", card.get("Expiry Date", "")))
        print(Fore.GREEN + format_line("🗓️", "Created At", card.get("Created At", "")))
        print(Fore.GREEN + format_line("🏦", "Bank Name", card.get("Bank Name", "")))

        print(Fore.GREEN + f"╠{'═' * width}╣")
        print(Fore.GREEN + f"║{'💸 Fees & Access':^{width}}║")
        print(Fore.GREEN + format_line("💰", "Joining Fee", card.get("Joining Fee", "")))
        print(Fore.GREEN + format_line("💼", "Annual Charges", card.get("Annual Charges", "")))
        print(Fore.GREEN + format_line("📌", "Paid or LTF", card.get("Paid or LTF", "")))
        print(Fore.GREEN + format_line("❌", "Need to Close", card.get("Need to Close", "")))
        print(Fore.GREEN + format_line("🛋️", "Lounge Access", card.get("Lounge Access", "")))
        print(Fore.GREEN + format_line("🌐", "Forex Markup", card.get("Forex Markup", "")))
        print(Fore.GREEN + format_line("🔐", "CVV", card.get("CVV", "")))

        print(Fore.GREEN + f"╠{'═' * width}╣")
        print(Fore.GREEN + f"║{'🌟 Special Benefits':^{width}}║")
        for line in card.get("Special Benefit", "").split("\n"):
            if line.strip():
                print(Fore.GREEN + format_bullet_line(line.strip()))

        print(Fore.GREEN + format_line("📅", "Due Date", card.get("Due Date", "")))
        print(Fore.GREEN + f"╠{'═' * width}╣")
        print(Fore.GREEN + f"║{'🧾 Spend History':^{width}}║")
        for spend in card.get("Spends", []):
            print(Fore.GREEN + format_bullet_line(f"{spend['Date']} - {spend['Name']} ₹{spend['Amount']}"))


        print(Fore.GREEN + f"╚{'═' * width}╝")


    @staticmethod
    def delete_card():
        cards = CardManager.load_all_cards()
        if not cards:
            print(Fore.YELLOW + "No cards to delete.")
            return

        table = [[idx + 1, card['Card Name'], card['Card Number'][-4:].rjust(len(card['Card Number']), "*")]
                 for idx, card in enumerate(cards)]
        print(Fore.CYAN + tabulate(table, headers=["No.", "Card Name", "Masked Number"], tablefmt="fancy_grid"))

        choice = input(Fore.CYAN + "\nEnter the number to delete (or 'q' to cancel): ")
        if choice.lower() == 'q':
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(cards)):
            print(Fore.RED + "Invalid selection.")
            return

        confirm = input(Fore.YELLOW + f"Are you sure to delete '{cards[int(choice)-1]['Card Name']}'? (y/n): ")
        if confirm.lower() != 'y':
            print(Fore.YELLOW + "Deletion cancelled.")
            return

        CardManager.delete_card(int(choice) - 1)

    @staticmethod
    def edit_card():
        cards = CardManager.load_all_cards()
        if not cards:
            print(Fore.YELLOW + "No cards to edit.")
            return

        table = [[idx + 1, card['Card Name'], card['Card Type'], card['Card Number'][-4:].rjust(len(card['Card Number']), "*"), card.get('Bank Name', '')] for idx, card in enumerate(cards)]
        print(Fore.CYAN + tabulate(table, headers=["No.", "Card Name", "Type", "Masked Number", "Bank"], tablefmt="fancy_grid"))

        choice = input(Fore.CYAN + "\nEnter the number of the card to edit (or 'q' to cancel): ")
        if choice.lower() == 'q':
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(cards)):
            print(Fore.RED + "Invalid selection.")
            return

        if not SecureStorage.verify_pin():
            return

        card = cards[int(choice) - 1]
        print(Fore.CYAN + "\n--- Edit Card Details ---")
        for field, current_value in card.items():
            new_value = input(f"{field} [{current_value}]: ").strip()
            if new_value:
                card[field] = new_value

        CardManager.update_card(int(choice) - 1, card)

    @staticmethod
    def search_cards():
        cards = CardManager.load_all_cards()
        if not cards:
            print(Fore.YELLOW + "No cards to search.")
            return

        print(Fore.CYAN + "\n--- Search Cards ---")
        print("1. By Card Type")
        print("2. By Card Holder Name")
        print("3. Cancel")

        option = input("Choose an option (1-3): ")
        if option == "1":
            ctype = input("Enter card type: ").strip().capitalize()
            matched = [c for c in cards if c.get("Card Type", "").lower() == ctype.lower()]
        elif option == "2":
            holder = input("Enter card holder name (partial/full): ").strip().lower()
            matched = [c for c in cards if holder in c.get("Card Holder", "").lower()]
        else:
            return

        if not matched:
            print(Fore.YELLOW + "No matching cards found.")
            return

        print(Fore.GREEN + tabulate(
            [[c["Card Name"], c["Card Type"], c["Card Number"][-4:].rjust(len(c["Card Number"]), "*"), c["Card Holder"]]
             for c in matched],
            headers=["Card Name", "Type", "Masked Number", "Holder"],
            tablefmt="fancy_grid"
        ))


def main_menu():
    SecureStorage.ensure_key_exists()  # Ensure key is ready before anything else
    while True:
        print(Fore.MAGENTA + "\n====== Credit Card Manager ======")
        print("1. Add a New Card")
        print("2. List and View a Card")
        print("3. Edit a Card")
        print("4. Delete a Card")
        print("5. Search Cards")
        print("6. Add Spend to Card")
        print("6. Exit")

        choice = input(Fore.CYAN + "Choose an option (1-6): ")
        if choice == "1":
            CardCLI.add_card()
        elif choice == "2":
            CardCLI.list_and_view()
        elif choice == "3":
            CardCLI.edit_card()
        elif choice == "4":
            CardCLI.delete_card()
        elif choice == "5":
            CardCLI.search_cards()
        elif choice == "6":
            CardCLI.add_spend()
        elif choice == "7":
            print(Fore.GREEN + "Goodbye!")
            break
        else:
            print(Fore.RED + "Invalid choice. Please select a valid option.")


if __name__ == "__main__":
    main_menu()
