from galacteek import log
from galacteek.dweb.page import BaseHandler
from galacteek.dweb.page import pyqtSlot
from galacteek.core.aservice import cached_property

from mode.utils.objects import cached_property  # noqa


class EthSmartContractHandler(BaseHandler):
    def __init__(self, contract, parent=None):
        super().__init__(parent)

        self.operator = contract

    @pyqtSlot(str, list, result=str)
    def ethCallTransact(self, fnName, args):
        log.debug(f'ethCallTransact: {fnName} ({args})')

        vargs = []
        for arg in args:
            if isinstance(arg, float):
                print('convert float ..', arg)
                vargs.append(int(arg))
            else:
                vargs.append(arg)

        receipt = self.operator.callFunctionTransact(
            fnName, *vargs)

        if receipt:
            log.debug(f'Receipt {dict(receipt)}')
            txHash = receipt.get('transactionHash')
            if txHash:
                return txHash.hex()

        return ''
