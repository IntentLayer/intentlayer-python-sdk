# did_client.py
from web3 import Web3

class DidRegistryClient:
    ABI = [...]  # forge build --json didregistry | jq .abi
    def __init__(self, rpc, address, acct):
        self.w3 = Web3(Web3.HTTPProvider(rpc))
        self.ct = self.w3.eth.contract(address=address, abi=self.ABI)
        self.acct = self.w3.eth.account.from_key(acct)

    def register(self, did:str):
        tx = self.ct.functions.register(did).build_transaction({
            "from": self.acct.address,
            "nonce": self.w3.eth.get_transaction_count(self.acct.address)
        })
        signed = self.acct.sign_transaction(tx)
        return self.w3.eth.send_raw_transaction(signed.rawTransaction)