from PyQt5.QtWidgets import QSizePolicy

from PyQt5.QtChart import QChartView
from PyQt5.QtChart import QChart
from PyQt5.QtChart import QLineSeries
from PyQt5.QtChart import QDateTimeAxis
from PyQt5.QtChart import QValueAxis

from PyQt5.QtGui import QColor
from PyQt5.QtGui import QPen
from PyQt5.QtGui import QPainter

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QDateTime
from PyQt5.QtCore import QCoreApplication


from galacteek import AsyncSignal

from .i18n import iPeers


def iBandwidthUsage():
    return QCoreApplication.translate(
        'BandwidthGraph', 'IPFS bandwidth usage')


def iRateKbPerSecond():
    return QCoreApplication.translate(
        'BandwidthGraph', 'Rate (kb/s)')


def iRateInput():
    return QCoreApplication.translate(
        'BandwidthGraph', 'Input')


def iRateOutput():
    return QCoreApplication.translate(
        'BandwidthGraph', 'Output')


class BaseTimedGraph(QChartView):
    def __init__(self, chart=None, parent=None):
        super(BaseTimedGraph, self).__init__(parent)
        self.setObjectName('BaseGraph')

        self.seriesPurgedT = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.chart = chart if chart else QChart()

        self.setRenderHint(QPainter.Antialiasing)

        self.axisX = QDateTimeAxis()
        self.axisX.setTickCount(5)
        self.axisX.setFormat('hh:mm:ss')
        self.axisX.setTitleText('Time')
        self.chart.addAxis(self.axisX, Qt.AlignBottom)

        self.axisY = QValueAxis()
        self.axisY.setLabelFormat('%i')
        self.axisY.setMin(0)
        self.axisY.setMax(1024)

        self.chart.addAxis(self.axisY, Qt.AlignLeft)

    def removeOldSeries(self, series, before: int):
        for point in series.pointsVector():
            if point.x() < before:
                series.remove(point)

    async def onBwStats(self, stats):
        pass


class BandwidthGraphView(BaseTimedGraph):
    bwStatsFetched = AsyncSignal(dict)

    def __init__(self, parent=None):
        super(BandwidthGraphView, self).__init__(parent=parent)

        self.setObjectName('BandwidthGraph')
        self.chart.setTitle(iBandwidthUsage())
        self.axisY.setTitleText(iRateKbPerSecond())

        self.bwStatsFetched.connectTo(self.onBwStats)

        penIn = QPen(QColor('red'))
        penIn.setWidth(2)
        penOut = QPen(QColor('blue'))
        penOut.setWidth(2)

        self.seriesKbIn = QLineSeries()
        self.seriesKbIn.setName(iRateInput())
        self.seriesKbIn.setPen(penIn)
        self.chart.addSeries(self.seriesKbIn)
        self.seriesKbIn.attachAxis(self.axisX)
        self.seriesKbIn.attachAxis(self.axisY)

        self.seriesKbOut = QLineSeries()
        self.seriesKbOut.setName(iRateOutput())
        self.seriesKbOut.setPen(penOut)
        self.chart.addSeries(self.seriesKbOut)
        self.seriesKbOut.attachAxis(self.axisX)
        self.seriesKbOut.attachAxis(self.axisY)

        self.setChart(self.chart)

    async def onBwStats(self, stats):
        dtNow = QDateTime.currentDateTime()
        dtMsecs = dtNow.toMSecsSinceEpoch()

        delta = 120 * 1000
        if not self.seriesPurgedT or (dtMsecs - self.seriesPurgedT) > delta:
            self.removeOldSeries(self.seriesKbIn, dtMsecs - delta)
            self.removeOldSeries(self.seriesKbOut, dtMsecs - delta)
            self.seriesPurgedT = dtMsecs

        rateIn = stats.get('RateIn', 0)
        rateOut = stats.get('RateOut', 0)
        rateInKb = int(rateIn / 1024)
        rateOutKb = int(rateOut / 1024)

        inVector = self.seriesKbIn.pointsVector()
        outVector = self.seriesKbIn.pointsVector()

        inValues = [p.y() for p in inVector]
        outValues = [p.y() for p in outVector]

        if inValues or outValues:
            self.axisY.setMax(max(max(inValues), max(outValues)))

        dateMin = QDateTime.fromMSecsSinceEpoch(dtMsecs - (30 * 1000))
        dateMax = QDateTime.fromMSecsSinceEpoch(dtMsecs + 2000)

        self.seriesKbIn.append(dtMsecs, rateInKb)
        self.seriesKbOut.append(dtMsecs, rateOutKb)
        self.axisX.setRange(dateMin, dateMax)


class PeersCountGraphView(BaseTimedGraph):
    peersCountFetched = AsyncSignal(int)

    def __init__(self, parent=None):
        super(PeersCountGraphView, self).__init__(parent=parent)

        self.setObjectName('PeersCountGraph')
        self.peersCountFetched.connectTo(self.onPeersCount)
        self.axisY.setTitleText(iPeers())

        pen = QPen(QColor('#60cccf'))
        pen.setWidth(2)

        self.seriesPeers = QLineSeries()
        self.seriesPeers.setName('Peers')
        self.seriesPeers.setPen(pen)
        self.chart.addSeries(self.seriesPeers)
        self.seriesPeers.attachAxis(self.axisX)
        self.seriesPeers.attachAxis(self.axisY)

        self.setChart(self.chart)

    async def onPeersCount(self, count):
        dtNow = QDateTime.currentDateTime()
        dtMsecs = dtNow.toMSecsSinceEpoch()

        delta = 120 * 1000
        if not self.seriesPurgedT or (dtMsecs - self.seriesPurgedT) > delta:
            self.removeOldSeries(self.seriesPeers, dtMsecs - delta)
            self.seriesPurgedT = dtMsecs

        peersVector = self.seriesPeers.pointsVector()
        values = [p.y() for p in peersVector]

        if values:
            self.axisY.setMax(max(values) + 10)
            self.axisY.setMin(min(values) - 10)

        dateMin = QDateTime.fromMSecsSinceEpoch(dtMsecs - (30 * 1000))
        dateMax = QDateTime.fromMSecsSinceEpoch(dtMsecs + 2000)

        self.seriesPeers.append(dtMsecs, count)
        self.axisX.setRange(dateMin, dateMax)
