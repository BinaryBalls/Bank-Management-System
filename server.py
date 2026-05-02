import json
import random
import string
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# ─── Bank Logic ───────────────────────────────────────────────────

class Bank:
    DATABASE = 'data.json'

    @classmethod
    def load_data(cls):
        p = Path(cls.DATABASE)
        if p.exists() and p.stat().st_size > 0:
            with open(cls.DATABASE, 'r') as f:
                return json.load(f)
        return []

    @classmethod
    def save_data(cls, data):
        with open(cls.DATABASE, 'w') as f:
            json.dump(data, f, indent=4)

    @classmethod
    def generate_account_number(cls):
        data = cls.load_data()
        existing = {u['account_no'] for u in data}
        while True:
            chars = random.choices(string.ascii_uppercase, k=3) + random.choices(string.digits, k=5)
            random.shuffle(chars)
            acc_no = 'AC' + ''.join(chars)
            if acc_no not in existing:
                return acc_no

    @classmethod
    def create_account(cls, name, age, email, pin):
        if not name.strip():
            return None, "Name cannot be empty."
        if age < 18:
            return None, "Age must be 18 or above."
        if not str(pin).isdigit() or len(str(pin)) != 4:
            return None, "PIN must be exactly 4 digits."
        if '@' not in email or '.' not in email:
            return None, "Invalid email address."
        data = cls.load_data()
        if any(u['email'] == email for u in data):
            return None, "An account with this email already exists."
        user = {
            "name": name.strip(),
            "age": age,
            "email": email.strip(),
            "pin": int(pin),
            "account_no": cls.generate_account_number(),
            "balance": 0,
            "transactions": []
        }
        data.append(user)
        cls.save_data(data)
        return user, "Account created successfully."

    @classmethod
    def find_user(cls, acc_no, pin):
        for user in cls.load_data():
            if user['account_no'] == acc_no and user['pin'] == int(pin):
                return user
        return None

    @classmethod
    def deposit(cls, acc_no, pin, amount):
        if amount <= 0:
            return False, "Amount must be greater than 0."
        if amount > 100000:
            return False, "Cannot deposit more than 1,00,000 at once."
        data = cls.load_data()
        for user in data:
            if user['account_no'] == acc_no and user['pin'] == int(pin):
                user['balance'] += amount
                user['transactions'].append({"type": "deposit", "amount": amount})
                cls.save_data(data)
                return True, f"Deposited {amount}. New balance: {user['balance']}"
        return False, "Invalid account number or PIN."

    @classmethod
    def withdraw(cls, acc_no, pin, amount):
        if amount <= 0:
            return False, "Amount must be greater than 0."
        data = cls.load_data()
        for user in data:
            if user['account_no'] == acc_no and user['pin'] == int(pin):
                if user['balance'] < amount:
                    return False, f"Insufficient balance. Available: {user['balance']}"
                user['balance'] -= amount
                user['transactions'].append({"type": "withdrawal", "amount": amount})
                cls.save_data(data)
                return True, f"Withdrawn {amount}. New balance: {user['balance']}"
        return False, "Invalid account number or PIN."

    @classmethod
    def transfer(cls, sender_acc, pin, receiver_acc, amount):
        if sender_acc == receiver_acc:
            return False, "Cannot transfer to the same account."
        if amount <= 0:
            return False, "Amount must be greater than 0."
        data = cls.load_data()
        sender = next((u for u in data if u['account_no'] == sender_acc and u['pin'] == int(pin)), None)
        receiver = next((u for u in data if u['account_no'] == receiver_acc), None)
        if not sender:
            return False, "Invalid sender account or PIN."
        if not receiver:
            return False, "Receiver account not found."
        if sender['balance'] < amount:
            return False, f"Insufficient balance. Available: {sender['balance']}"
        sender['balance'] -= amount
        receiver['balance'] += amount
        sender['transactions'].append({"type": "transfer_out", "to": receiver_acc, "amount": amount})
        receiver['transactions'].append({"type": "transfer_in", "from": sender_acc, "amount": amount})
        cls.save_data(data)
        return True, f"Transferred {amount} to {receiver['name']} successfully."

    @classmethod
    def get_transactions(cls, acc_no, pin):
        user = cls.find_user(acc_no, pin)
        if not user:
            return None, "Invalid account or PIN."
        return user['transactions'], "OK"

    @classmethod
    def update_user(cls, acc_no, pin, name=None, email=None, new_pin=None):
        if new_pin and (not str(new_pin).isdigit() or len(str(new_pin)) != 4):
            return False, "New PIN must be exactly 4 digits."
        data = cls.load_data()
        for user in data:
            if user['account_no'] == acc_no and user['pin'] == int(pin):
                if name: user['name'] = name.strip()
                if email:
                    if '@' not in email or '.' not in email:
                        return False, "Invalid email address."
                    user['email'] = email.strip()
                if new_pin: user['pin'] = int(new_pin)
                cls.save_data(data)
                return True, "Account updated successfully."
        return False, "Invalid account or PIN."

    @classmethod
    def delete_account(cls, acc_no, pin):
        data = cls.load_data()
        for i, user in enumerate(data):
            if user['account_no'] == acc_no and user['pin'] == int(pin):
                data.pop(i)
                cls.save_data(data)
                return True, "Account deleted successfully."
        return False, "Invalid account or PIN."


# ─── HTTP Handler ─────────────────────────────────────────────────

class BankHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ('/', '/index.html'):
            try:
                with open('index.html', 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Content-Length', len(content))
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_json({'error': 'index.html not found'}, 404)
        else:
            self.send_json({'error': 'Not found'}, 404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except Exception:
            self.send_json({'error': 'Invalid JSON'}, 400)
            return

        path = urlparse(self.path).path

        if path == '/api/create':
            user, msg = Bank.create_account(
                data.get('name', ''),
                int(data.get('age', 0)),
                data.get('email', ''),
                str(data.get('pin', ''))
            )
            if user:
                self.send_json({'success': True, 'message': msg, 'account_no': user['account_no'], 'name': user['name']})
            else:
                self.send_json({'success': False, 'message': msg})

        elif path == '/api/login':
            user = Bank.find_user(data.get('account_no', ''), str(data.get('pin', '')))
            if user:
                self.send_json({'success': True, 'name': user['name'], 'balance': user['balance'],
                                'account_no': user['account_no'], 'email': user['email'], 'age': user['age']})
            else:
                self.send_json({'success': False, 'message': 'Invalid account number or PIN.'})

        elif path == '/api/deposit':
            ok, msg = Bank.deposit(data.get('account_no', ''), str(data.get('pin', '')), int(data.get('amount', 0)))
            self.send_json({'success': ok, 'message': msg})

        elif path == '/api/withdraw':
            ok, msg = Bank.withdraw(data.get('account_no', ''), str(data.get('pin', '')), int(data.get('amount', 0)))
            self.send_json({'success': ok, 'message': msg})

        elif path == '/api/transfer':
            ok, msg = Bank.transfer(
                data.get('account_no', ''), str(data.get('pin', '')),
                data.get('receiver_acc', ''), int(data.get('amount', 0))
            )
            self.send_json({'success': ok, 'message': msg})

        elif path == '/api/transactions':
            txns, msg = Bank.get_transactions(data.get('account_no', ''), str(data.get('pin', '')))
            if txns is None:
                self.send_json({'success': False, 'message': msg})
            else:
                self.send_json({'success': True, 'transactions': txns})

        elif path == '/api/update':
            ok, msg = Bank.update_user(
                data.get('account_no', ''), str(data.get('pin', '')),
                data.get('name') or None, data.get('email') or None,
                str(data.get('new_pin', '')) if data.get('new_pin') else None
            )
            self.send_json({'success': ok, 'message': msg})

        elif path == '/api/delete':
            ok, msg = Bank.delete_account(data.get('account_no', ''), str(data.get('pin', '')))
            self.send_json({'success': ok, 'message': msg})

        else:
            self.send_json({'error': 'Unknown endpoint'}, 404)


# ─── Start Server ─────────────────────────────────────────────────

if __name__ == '__main__':
    PORT = 8000
    server = HTTPServer(('localhost', PORT), BankHandler)
    print(f"🏦 Bank server running at http://localhost:{PORT}")
    print("   Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n Server stopped.")