from eth_account import Account

Account.enable_unaudited_hdwallet_features()


def createWithMnemonic():
    acct, mnemonic = Account.create_with_mnemonic()
    return acct, mnemonic


def accountFromKey(key):
    return Account.from_key(key)
