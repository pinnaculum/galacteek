const options = {
    keepAlive: true,
    timeout: 20000,
};

window.ethereum = new Web3.providers.HttpProvider('@RPCURL@', options);

const web3 = new Web3(window.ethereum);

let account = web3.eth.accounts.create(web3.utils.randomHex(32));

let wallet = web3.eth.accounts.wallet.add(account);

let keystore = wallet.encrypt(web3.utils.randomHex(32));

web3.eth.defaultAccount = account.address;

window.ethereum.request = async (request) => {
    console.debug('web3 Request: ' + request.method);

    return new Promise(async (resolve, reject) => {
      /*
      if (request.method === 'eth_requestAccounts') {
          console.debug('Request is eth_requestAccounts');

          web3.eth.getAccounts().then(console.log);
          resolve({
            result: []
          });
      }
      */

      web3.currentProvider.send({
        jsonrpc: '2.0',
        id: 0,
        method: request.method,
        params: request.params
      }, (err, result) => {
          console.debug('RESULT IS : ' + JSON.stringify(result));
          resolve(result);
      });
    });
};

window.ethereum.enable = async () => {
  /* Deprecated */
};
