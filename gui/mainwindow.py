# -*- coding: utf8 -*-

from PyQt4 import QtGui
from PyQt4 import QtCore
from gui.menu import menu
from gui.newmapdialog import newMapDialog
from gui.exportmapdialog import exportMapDialog
from gui.specieslistdialog import speciesListDialog
from gui.addplacedialog import addPlaceDialog
from gui.placeslist import placesList
from core import worker
import imghdr
import os


class mainWindow(QtGui.QMainWindow):
	"""
	Class for the main window of the application.
	"""

	_instance = None
	_imageScene = None
	_scrollArea = None
	_scaleFactor = 1.0

	_isRecording = False

	_selectPixelEvent = QtCore.pyqtSignal(int, int)
	_selectedCellRect = None
	_pixmaps = dict()

	_placesWidget = None

	_thread = None

	def __new__(cls, *args, **kwargs):
		if not cls._instance:
			cls._instance = super(mainWindow, cls).__new__(
								cls, *args, **kwargs)
		return cls._instance

	@classmethod
	def getInstance(cls):
		return cls._instance

	def __init__(self, app):
		"""
		Class's construct.

		@param app QtGui.QApplication Application containing the window.
		"""
		super(mainWindow, self).__init__()
		self._app = app
		self.addWidget = None
		#creation of the UI
		self.initUI()
		self.initSignals()

	def initUI(self):
		"""
		Initialization of the UI:
		- creation of the menu bar,
		- creation of the status bar,
		- creation of the window's content,
		- definition of the window informations (size, position),
		- display of the window.
		"""
		#top menu
		self.setMenuBar(menu(self))
		self.setStatusBar(QtGui.QStatusBar())
		#creation fo the window
		self._create()
		#definition if window informations (size, position, title)
		self._setWindowInfos()
		#display the Whole Thing
		self.show()

	def initSignals(self):
		"""
		Method which initialise some signals.
		For the moment, the only signal is the application's mapOpened,
		triggered when a map file is opened. At this moment, the places' widget
		is populated to list the existing places.
		"""
		self._app.mapOpened.connect(self._placesWidget.setData)

	def _create(self):
		"""
		Method which create the UI
		The window elements are created here.
		For the moment, the window contains only a QGraphicsView displaying the
		world's map.
		"""

		splitter = QtGui.QSplitter()
		splitter.setOrientation(QtCore.Qt.Orientation(QtCore.Qt.Horizontal))

		self._placesWidget = placesList(self, self._app)

		self._imageScene = QtGui.QGraphicsScene()
		self._imageView = QtGui.QGraphicsView()
		self._imageView.setScene(self._imageScene)

		splitter.addWidget(self._placesWidget)
		splitter.addWidget(self._imageView)
		splitter.setStretchFactor(1, 1)
		self.setCentralWidget(splitter)

	def displayMessage(self, text):
		"""
		Displays a message in the status bar.
		"""
		self.statusBar().showMessage(text)

	def _setWindowInfos(self):
		"""
		Define window informations
		"""
		# default size
		self.setGeometry(300, 300, 600, 600)
		#~ self.setWidth()
		self.setWindowTitle('World editor')

	def newMap(self):
		"""
		Action triggered when the menu's "new" button is pressed.
		The user is then invited to select a map name and size.
		"""
		newmap = newMapDialog(self, self._app)

	def openMapAction(self):
		"""
		Action triggered when the menu's "open" button is pressed.
		The user is then invited to select a map on his computer. The map must
		be a picture file.
		"""
		fileName = QtGui.QFileDialog.getOpenFileName(
			self,
			"Open file",
			QtCore.QDir.currentPath(),
			"Maps (*.map)"
		)

		if fileName == "":
			return

		try:
			self._app.openMap(fileName)
			self.openMap()
		except BaseException as e:
			self.alert(e.message)

	def zoomInMap(self):
		"""
		Wrapper method to zoom in the map, calls scaleImage().
		"""
		self._scaleFactor *= 1.25
		self.scaleImage()

	def zoomOutMap(self):
		"""
		Wrapper method to zoom out the map, calls scaleImage().
		"""
		self._scaleFactor *= 0.75
		self.scaleImage()

	def scaleImage(self):
		"""
		Method to resize the map after a zoom action.
		Once the map is resized, if the scale factor is lower or equal than
		0.75, the zoom out button is disabled and if the scale factor is higher
		or equal than 30.0, the zoom in button is disabled.
		"""
		self._imageView.resetTransform()
		transform = self._imageView.transform()
		transform.scale(self._scaleFactor, self._scaleFactor)
		self._imageView.setTransform(transform)

		self.menuBar().mapZoomed.emit(self._scaleFactor)

	def pixelSelect(self, event):
		"""
		Action called when the map is clicked, to get the clicked pixel.
		"""
		(x, y) = (int(event.pos().x()), int(event.pos().y()))
		self._selectPixelEvent.emit(x, y)

	def openMap(self):
		"""
		Method to open a map from a filename
		"""
		fileName = self._app.getMapFileName() + '.bmp'

		image = QtGui.QImage(fileName)
		if image is None or imghdr.what(str(fileName)) != "bmp":
			QtGui.QMessageBox.information(
				self,
				"Image Viewer",
				"Cannot open %s." % (fileName)
			)
			return

		self._imageScene.clear()
		mapPixmap = QtGui.QPixmap.fromImage(image)
		mapPixmap = QtGui.QGraphicsPixmapItem(mapPixmap, None, self._imageScene)
		mapPixmap.mousePressEvent = self.pixelSelect

		self._pixmaps = dict()
		self._pixmaps['map'] = mapPixmap

		for p in self._app.map.places:
			self.displayPlace(p['coordinates'][0], p['coordinates'][1])

		if self._app.map.startCellPosition is not None:
			self.displayStartCell(self._app.map.startCellPosition[0], self._app.map.startCellPosition[1])

		self._scaleFactor = 1.0

		self.menuBar().mapOpened.emit()

	def exportMap(self):
		"""
		Method to export a map.
		Will check if the map can be exported, and if it is, the export will be
		run and a dialog will be displayed with a progress bar to show the
		export progression.
		"""
		try:
			self._app.map.checkForExport()
		except BaseException as e:
			self.alert(e.message)
			return

		exportDialog = exportMapDialog(self)

		self._thread = worker.exporterThread(self._app)
		self._thread.finished.connect(exportDialog.close)
		self._thread.exportError.connect(self.alert)

		exportDialog.setThread(self._thread)
		self._thread.start()

	def recordSelectStartCell(self):
		"""
		Method called when the user has to select a starting cell. A record mode
		will be enabled and the user will have to click on a cell in the map.
		"""
		if not self.isRecording():
			self.enableRecordingMode()
			self._selectPixelEvent.connect(self.selectStartCell)

	def recordAddPlaceCell(self):
		"""
		Method called when the user has to select a cell to add a place in the
		world. A record mode will be enabled and the user will have to click on
		a cell in the map
		"""
		if not self.isRecording():
			self.enableRecordingMode()
			self._selectPixelEvent.connect(self.addPlace)

	def selectStartCell(self, x, y):
		"""
		Method called when the user click on a cell in the map to select a
		starting cell.
		"""
		try:
			self._app.map.setStartCellPosition((x, y))
			self.displayStartCell(x, y)
		except BaseException as e:
			self.alert(e.message)

		self.disableRecordingMode()
		self._selectPixelEvent.disconnect(self.selectStartCell)

	def displayStartCell(self, x, y):
		"""
		Here the start cell is displayed in the map, as a new pixmap
		"""
		if 'start-cell' in self._pixmaps.keys():
			self._imageScene.removeItem(self._pixmaps['start-cell'])
			self._pixmaps['start-cell'] = None

		rect = QtGui.QGraphicsRectItem(x, y, 1, 1, None, self._imageScene)
		rect.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0)))
		self._pixmaps['start-cell'] = rect

	def addPlace(self, x, y):
		"""
		Method called when the user click on a cell in the map to add a place.
		"""

		if not self._app.map.isCellOnLand((x, y)):
			self.alert("No place can be added in water")
			return

		dialog = addPlaceDialog(self, self._app, (x, y))
		dialog.placeAdded.connect(self.displayPlace)
		dialog.placeAdded.connect(self._placesWidget.setData)

		self.disableRecordingMode()
		self._selectPixelEvent.disconnect(self.addPlace)

	def displayPlace(self, x, y):
		"""
		This method creates a pixmap in the map for each place of the map.
		"""
		if 'places' not in self._pixmaps.keys():
			self._pixmaps['places'] = list()

		rect = QtGui.QGraphicsRectItem(x, y, 1, 1, None, self._imageScene)
		rect.setBrush(QtGui.QBrush(QtGui.QColor(127, 127, 127)))
		rect.setPen(QtGui.QPen(QtGui.QColor(127, 127, 127)))
		self._pixmaps['places'].append(rect)

	def alert(self, message):
		"""
		Method to display an alert message. Create just an critical QMessageBox.
		"""
		QtGui.QMessageBox.critical(self, "An error occured", message)

	def listspecies(self):
		"""
		Method called to display a dialog listing the map's species.
		"""
		specieswindow = speciesListDialog(self, self._app)
		specieswindow.show()

	def selectCell(self, x, y):
		"""
		This method is called when the record mode is enabled and a cell of
		the map is clicked. At this moment, the cell is highlighted with a
		black border arround it.
		"""
		if self._selectedCellRect is not None:
			self.unselectCell()

		self._selectedCellRect = QtGui.QGraphicsRectItem(x, y, 1, 1, None, self._imageScene)
		self._selectedCellRect.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))

	def unselectCell(self):
		"""
		Method to remove the pixel of the previously selected cell.
		"""
		self._imageScene.removeItem(self._selectedCellRect)
		self._selectedCellRect = None

	def isRecording(self):
		"""
		Method to know if the recording mode is enabled.
		"""
		return self._isRecording

	def enableRecordingMode(self):
		"""
		Method to enable the recording mode.
		"""
		self._isRecording = True
		self._selectPixelEvent.connect(self.selectCell)

	def disableRecordingMode(self):
		"""
		Method to disable the recording mode.
		"""
		self._isRecording = False
		self._selectPixelEvent.disconnect(self.selectCell)

	def centerMapOnCoordinates(self, coordinates):
		"""
		This method does a maximum zoom on a selected cell of the map.
		"""
		self._imageView.fitInView(coordinates[0] - 1, coordinates[1] - 1, 3, 3)
		self._scaleFactor = 30.0
		self.scaleImage()

	def saveMapAction(self):
		"""
		This method is called when the "Save" button from the menu is pressed.
		If the map's save file name is set, the map is saved in this file,
		else the "Save as" action is called.
		"""
		if self._app.getSaveFileName() is None:
			self.saveMapAsAction()
		else:
			self._app.saveMap()

	def saveMapAsAction(self):
		"""
		This method asks the user to select a file on his computer, and then
		save the map in this file.`
		"""
		fileName = QtGui.QFileDialog.getSaveFileName(
			self,
			"Select file",
			QtCore.QDir.currentPath(),
			"Map (*.map)"
		)

		if fileName[-4:] != '.map':
			fileName = fileName + '.map'

		self._app.setSaveMapName(fileName)
		self._app.saveMap()
