# Author: William Liu <liwi@ohsu.edu>

from PySide6.QtCore import QStandardPaths, Qt, QUrl, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    """The Main Window of the application."""

    def __init__(self) -> None:
        super().__init__()

        # Widgets for video and audio playback
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

        # Filename builder widgets
        self._side_id_label = QLabel("Site ID", parent=self)
        self._site_id_combobox = QComboBox(parent=self)
        self._site_id_combobox.addItems(
            ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "Rochester"]
        )

        self._subject_id_label = QLabel("Subject ID", parent=self)
        self._subject_id_spinbox = QSpinBox(parent=self)
        self._subject_id_spinbox.setRange(0, 999)

        self._freezer_status_label = QLabel("Freezer Status", parent=self)
        self._freezer_status_combobox = QComboBox(parent=self)
        self._freezer_status_combobox.addItems(["FR", "NF", "CO"])

        self._session_id_label = QLabel("Session ID", parent=self)
        self._session_id_combobox = QComboBox(parent=self)
        self._session_id_combobox.addItems(["ses01", "ses02"])

        self._medication_status_label = QLabel("On/Off", parent=self)
        self._medication_status_combobox = QComboBox(parent=self)
        self._medication_status_combobox.addItems(["on", "off"])

        self._trial_id_label = QLabel("Trial ID", parent=self)
        self._trial_id_combobox = QComboBox(parent=self)
        self._trial_id_combobox.addItems(
            [
                "stwalk",
                "dtwalk",
                "stcarr",
                "stturn",
                "dtturn",
                "stshuf",
                "stagil",
                "stdoor",
            ]
        )

        self._retry_label = QLabel("Retry (leave 0 if N/A)", parent=self)
        self._retry_spinbox = QSpinBox(parent=self)
        self._retry_spinbox.setRange(0, 999)

        self._video_plane_label = QLabel("Video Plane", parent=self)
        self._video_plane_combobox = QComboBox(parent=self)
        self._video_plane_combobox.addItems(["front", "sagit"])

        self._add_to_queue_button = QPushButton("Add to queue", parent=self)
        self._add_to_queue_button.clicked.connect(self.enqueue)

        filename_builder_layout = QGridLayout()
        filename_builder_layout.addWidget(self._side_id_label, 0, 0)
        filename_builder_layout.addWidget(self._site_id_combobox, 0, 1)
        filename_builder_layout.addWidget(self._subject_id_label, 1, 0)
        filename_builder_layout.addWidget(self._subject_id_spinbox, 1, 1)
        filename_builder_layout.addWidget(self._freezer_status_label, 2, 0)
        filename_builder_layout.addWidget(self._freezer_status_combobox, 2, 1)
        filename_builder_layout.addWidget(self._session_id_label, 3, 0)
        filename_builder_layout.addWidget(self._session_id_combobox, 3, 1)
        filename_builder_layout.addWidget(self._medication_status_label, 4, 0)
        filename_builder_layout.addWidget(self._medication_status_combobox, 4, 1)
        filename_builder_layout.addWidget(self._trial_id_label, 5, 0)
        filename_builder_layout.addWidget(self._trial_id_combobox, 5, 1)
        filename_builder_layout.addWidget(self._retry_label, 6, 0)
        filename_builder_layout.addWidget(self._retry_spinbox, 6, 1)
        filename_builder_layout.addWidget(self._video_plane_label, 7, 0)
        filename_builder_layout.addWidget(self._video_plane_combobox, 7, 1)
        filename_builder_layout.addWidget(self._add_to_queue_button, 8, 0, 1, 2)

        # File queue widget
        self._queue = QTableWidget(parent=self)
        self._queue.setRowCount(0)
        self._queue.setColumnCount(2)
        self._queue.setHorizontalHeaderLabels(["Original File", "New Name"])
        horizontal_header = self._queue.horizontalHeader()
        horizontal_header.setSectionResizeMode(
            QHeaderView.Stretch
        )  # make cols fill available space

        # Layout for the video player
        video_player_layout = QVBoxLayout()
        video_player_layout.addWidget(self._video_label)
        video_player_layout.addWidget(self._video_widget, stretch=1)
        video_player_layout.addWidget(self._scrubber)

        # Layout for the file queue and filename builder
        queue_layout = QVBoxLayout()
        queue_layout.addLayout(filename_builder_layout)
        queue_layout.addWidget(self._queue)

        central_layout = QHBoxLayout()
        central_layout.addLayout(video_player_layout, stretch=1)
        central_layout.addLayout(queue_layout, stretch=1)
        self._central_widget = QWidget(parent=self)
        self._central_widget.setLayout(central_layout)
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
            self._audio_output.setVolume(0)
        else:
            self._media_player.setSource(QUrl())
            self._video_label.setText("No file selected")

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

    @Slot()
    def enqueue(self) -> None:
        local_path = self._media_player.source().toLocalFile()
        if local_path == "":
            return

        new_filename = self._build_filename()
        original_name = QTableWidgetItem(local_path)
        original_name.setFlags(~Qt.ItemIsEditable)
        new_name = QTableWidgetItem(new_filename)
        new_name.setFlags(~Qt.ItemIsEditable)
        num_rows = self._queue.rowCount()
        self._queue.setRowCount(num_rows + 1)
        self._queue.setItem(num_rows, 0, original_name)
        self._queue.setItem(num_rows, 1, new_name)

    def _build_filename(self) -> str:
        site_id = self._site_id_combobox.currentText()
        subject_id = self._subject_id_spinbox.value()
        freezer_status = self._freezer_status_combobox.currentText()
        session_id = self._session_id_combobox.currentText()
        medication_status = self._medication_status_combobox.currentText()
        trial_id = self._trial_id_combobox.currentText()
        retry = self._retry_spinbox.value()
        video_plane = self._video_plane_combobox.currentText()

        if retry == 0:
            return f"{site_id}_sub{subject_id:03d}_{freezer_status}_{session_id}_{medication_status}_{trial_id}_{video_plane}_blur.mp4"

        return f"{site_id}_sub{subject_id:03d}_{freezer_status}_{session_id}_{medication_status}_{trial_id}-retr{retry}_{video_plane}_blur.mp4"


if __name__ == "__main__":
    app = QApplication()
    main_window = MainWindow()
    available_geometry = main_window.screen().availableGeometry()
    main_window.resize(
        available_geometry.width() / 1.5, available_geometry.height() / 1.1
    )
    main_window.show()
    app.exec()
