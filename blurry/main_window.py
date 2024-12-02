# Author: William Liu <liwi@ohsu.edu>

from PySide6.QtCore import QStandardPaths, Qt, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QMainWindow,
    QSlider,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    """The Main Window of the application."""

    def __init__(self) -> None:
        super().__init__()

        self._media_player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._video_widget = QVideoWidget()
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.setVideoOutput(self._video_widget)
        self._media_player.errorOccurred.connect(self.player_error)
        self._media_player.playbackStateChanged.connect(self.update_media_buttons)
        self._media_player.positionChanged.connect(self.update_scrubber)
        self._media_player.durationChanged.connect(self.duration_changed)

        # Create the menu bar
        menu_bar = self.menuBar()
        open_action = QAction("&Open video file...", self)
        open_action.triggered.connect(self.open_video)
        menu_bar.addAction(open_action)

        # Create tool bar with media controls
        media_tool_bar = QToolBar(parent=self)
        media_tool_bar.setMovable(False)
        self.addToolBar(Qt.BottomToolBarArea, media_tool_bar)

        icon = QIcon.fromTheme(QIcon.ThemeIcon.MediaPlaybackStart)
        self._play_action = media_tool_bar.addAction(icon, "Play")
        self._play_action.triggered.connect(self._media_player.play)

        icon = QIcon.fromTheme(QIcon.ThemeIcon.MediaPlaybackPause)
        self._pause_action = media_tool_bar.addAction(icon, "Pause")
        self._pause_action.triggered.connect(self._media_player.pause)

        # Slider to scrub the video
        self._scrubber = QSlider(Qt.Horizontal, parent=self)
        self._scrubber.setRange(0, 0)
        self._scrubber.sliderPressed.connect(self._media_player.pause)
        self._scrubber.sliderReleased.connect(self.scrubber_released)

        # Label for video title
        self._video_label = QLabel("No file selected", parent=None)

        self._central_widget = QWidget(parent=self)
        layout = QVBoxLayout()
        layout.addWidget(self._video_label)
        layout.addWidget(self._video_widget, stretch=1)
        layout.addWidget(self._scrubber)
        self._central_widget.setLayout(layout)
        self.setCentralWidget(self._central_widget)

    def closeEvent(self, event):
        self._ensure_stopped()
        event.accept()

    @Slot()
    def open_video(self):
        self._ensure_stopped()
        file_dialog = QFileDialog(self)
        file_dialog.setMimeTypeFilters("video/mp4")
        movies_location = QStandardPaths.writableLocation(QStandardPaths.MoviesLocation)
        file_dialog.setDirectory(movies_location)
        if file_dialog.exec() == QDialog.Accepted:
            self._media_player.setSource(file_dialog.selectedUrls()[0])
            self._video_label.setText(file_dialog.selectedFiles()[0])
            self._media_player.play()

    def _ensure_stopped(self):
        if self._media_player.playbackState() != QMediaPlayer.StoppedState:
            self._media_player.stop()

    @Slot("QMediaPlayer::Error", str)
    def player_error(self, error, error_string):
        self.show_status_message(error_string)

    def show_status_message(self, message):
        self.statusBar().showMessage(message, 5000)

    @Slot("QMediaPlayer::PlaybackState")
    def update_media_buttons(self, state) -> None:
        self._play_action.setEnabled(state != QMediaPlayer.PlayingState)
        self._pause_action.setEnabled(state == QMediaPlayer.PlayingState)

    @Slot(int)
    def duration_changed(self, duration) -> None:
        self._scrubber.setRange(0, duration)

    @Slot(int)
    def update_scrubber(self, position) -> None:
        self._scrubber.setValue(position)

    @Slot()
    def scrubber_released(self) -> None:
        current_position = self._scrubber.value()
        self._media_player.setPosition(current_position)
        self._media_player.play()


if __name__ == "__main__":
    app = QApplication()
    main_window = MainWindow()
    available_geometry = main_window.screen().availableGeometry()
    main_window.resize(available_geometry.width() / 3, available_geometry.height() / 2)
    main_window.show()
    app.exec()
