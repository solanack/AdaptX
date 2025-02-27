import base58

# Replace with the array from bot_wallet.json
private_key_bytes = [200,3,137,26,25,241,9,74,210,151,73,68,157,202,30,65,137,153,184,56,161,75,83,14,95,196,45,183,219,233,25,77,144,148,198,66,245,5,231,196,107,221,46,97,184,211,24,54,121,68,247,113,237,206,55,72,118,75,83,181,147,109,214,22]  # Copy the exact array from bot_wallet.json
base58_key = base58.b58encode(bytes(private_key_bytes)).decode('utf-8')
print("Base58 Private Key:", base58_key)