# Author: William Liu <liwi@ohsu.edu>

import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from typing import Tuple

from progress_dialog import ProgressDialog
from PySide6.QtCore import (
    QCoreApplication,
    QStandardPaths,
    Qt,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """The Main Window of the application."""

    video_progress = Signal(int)
    frame_progress = Signal(int)
    total_frames = Signal(int)

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("JP-FOG blurry")

        # Store previously used video directory
        self._previous_dir = None

        # Flag for whether user has cancelled the blurring process
        self._cancel_blurring = False

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
        open_action = QAction("&Open video file...", parent=self)
        open_action.triggered.connect(self.open_video)
        menu_bar.addAction(open_action)
        menu_bar.setNativeMenuBar(False)

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

        # Slider to change volume
        self._volume_slider = QSlider(Qt.Horizontal, parent=self)
        available_width = self.screen().availableGeometry().width()
        self._volume_slider.setFixedWidth(available_width / 5)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(self._audio_output.volume())
        self._volume_slider.setTickInterval(10)
        self._volume_slider.setTickPosition(QSlider.TicksBelow)
        self._volume_slider.setToolTip("Volume")
        self._volume_slider.valueChanged.connect(
            lambda x: self._audio_output.setVolume(x / 100)
        )
        media_tool_bar.addWidget(self._volume_slider)

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
                "vostop",
                "custop",
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
        self._queue.setColumnCount(3)
        self._queue.setHorizontalHeaderLabels(
            ["Original File", "New Name", "Remove Row"]
        )
        horizontal_header = self._queue.horizontalHeader()
        horizontal_header.setSectionResizeMode(0, QHeaderView.Stretch)
        horizontal_header.setSectionResizeMode(1, QHeaderView.Stretch)
        horizontal_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        # Threshold Slider
        self._threshold_label = QLabel("Threshold value", parent=self)
        self._threshold_spinbox = QDoubleSpinBox(parent=self)
        self._threshold_spinbox.setMinimum(0.01)
        self._threshold_spinbox.setValue(0.25)
        self._threshold_spinbox.setSingleStep(0.01)

        # Blur faces button
        self._run_blurring_button = QPushButton("Run blurring...", parent=self)
        self._run_blurring_button.clicked.connect(self.blur_videos)

        # Layout for the video player
        video_player_layout = QVBoxLayout()
        video_player_layout.addWidget(self._video_label)
        video_player_layout.addWidget(self._video_widget, stretch=1)
        video_player_layout.addWidget(self._scrubber)

        # Layout for the file queue and filename builder
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(self._threshold_label)
        threshold_layout.addWidget(self._threshold_spinbox)
        queue_layout = QVBoxLayout()
        queue_layout.addLayout(filename_builder_layout)
        queue_layout.addWidget(self._queue)
        queue_layout.addLayout(threshold_layout)
        queue_layout.addWidget(self._run_blurring_button)

        central_layout = QHBoxLayout()
        central_layout.addLayout(video_player_layout, stretch=1)
        central_layout.addLayout(queue_layout, stretch=1)
        self._central_widget = QWidget(parent=self)
        self._central_widget.setLayout(central_layout)
        self.setCentralWidget(self._central_widget)

    def closeEvent(self, event):
        self._ensure_stopped()
        logger.info("Application closed.")
        event.accept()

    @Slot()
    def open_video(self):
        logger.debug("Open video file menu button pressed.")
        self._ensure_stopped()
        file_dialog = QFileDialog(self)
        movies_location = (
            QStandardPaths.writableLocation(QStandardPaths.MoviesLocation)
            if self._previous_dir is None
            else self._previous_dir
        )
        file_dialog.setDirectory(movies_location)
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("Videos (*.mp4)")
        if file_dialog.exec() == QDialog.Accepted:
            self._media_player.setSource(file_dialog.selectedUrls()[0])
            self._video_label.setText(file_dialog.selectedFiles()[0])
            self._previous_dir = os.path.dirname(file_dialog.selectedFiles()[0])
            self._volume_slider.setValue(20)
            logger.info(f"{file_dialog.selectedFiles()[0]} was selected.")
            self._media_player.play()
        else:
            self._media_player.setSource(QUrl())
            self._video_label.setText("No file selected")
            logger.info("No file selected or file dialog closed.")

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
        logger.debug("Enqueue button pressed.")
        local_path = self._media_player.source().toLocalFile()
        if local_path == "":
            return
        if not self._verify_unique_filename(local_path, 0):
            msg = QMessageBox()
            msg.setText("Video file already in use!")
            msg.setInformativeText(
                "Cannot use the same source video file more than once."
            )
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Information!")
            msg.exec()
            return

        new_filename = self._build_filename()
        if not self._verify_unique_filename(new_filename, 1):
            msg = QMessageBox()
            msg.setText("Filename already in use!")
            msg.setInformativeText(
                "Cannot create two videos with the same filename. Check the options and try again."
            )
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Information!")
            msg.exec()
            return

        original_name = QTableWidgetItem(local_path)
        original_name.setFlags(~Qt.ItemIsEditable)
        original_name.setToolTip(local_path)
        new_name = QTableWidgetItem(new_filename)
        new_name.setFlags(~Qt.ItemIsEditable)
        new_name.setToolTip(new_filename)
        delete_button = QPushButton("Remove", parent=self._queue)
        delete_button.clicked.connect(self.remove_row)
        num_rows = self._queue.rowCount()
        # Create a custom property so each button knows what row to operate on
        delete_button.setProperty("Row", num_rows)
        self._queue.setRowCount(num_rows + 1)
        self._queue.setItem(num_rows, 0, original_name)
        self._queue.setItem(num_rows, 1, new_name)
        self._queue.setCellWidget(num_rows, 2, delete_button)
        self._queue.scrollToBottom()

    def _build_filename(self) -> str:
        site_id = self._site_id_combobox.currentText()
        if site_id == "Rochester":
            site_id = ""
        else:
            site_id += "_"

        subject_id = self._subject_id_spinbox.value()
        freezer_status = self._freezer_status_combobox.currentText()
        session_id = self._session_id_combobox.currentText()
        medication_status = self._medication_status_combobox.currentText()
        trial_id = self._trial_id_combobox.currentText()
        retry = self._retry_spinbox.value()
        video_plane = self._video_plane_combobox.currentText()

        if retry == 0:
            return (
                f"{site_id}sub{subject_id:03d}_{freezer_status}_{session_id}_"
                f"{medication_status}_{trial_id}_{video_plane}_blur.mp4"
            )

        return (
            f"{site_id}sub{subject_id:03d}_{freezer_status}_{session_id}_"
            f"{medication_status}_{trial_id}-retr{retry}_{video_plane}_blur.mp4"
        )

    def _verify_unique_filename(self, prop: str, col: int) -> bool:
        for row in range(self._queue.rowCount()):
            name = self._queue.item(row, col).text()
            if prop == name:
                return False

        return True

    @Slot()
    def remove_row(self) -> None:
        # Retrieve the button's Row property to know which row to delete
        sender_row = self.sender().property("Row")
        self._queue.removeRow(sender_row)
        QCoreApplication.processEvents()
        self._update_row_property()

    def _update_row_property(self) -> None:
        for row in range(self._queue.rowCount()):
            delete_button = self._queue.cellWidget(row, 2)
            delete_button.setProperty("Row", row)

    @Slot()
    def blur_videos(self) -> None:
        # Reset the cancel flag
        self._cancel_blurring = False

        # Read the currently set threshold
        threshold = self._threshold_spinbox.value()

        num_rows = self._queue.rowCount()
        if num_rows == 0:
            return

        export_dir = self._set_export_directory()
        if export_dir == "":
            logger.info("Export file dialog was closed or cancelled.")
            return
        if not self._verify_export_directory(export_dir):
            logger.info(
                "Export was directory was selected, but does not conform to expected directory structure"
            )
            msg = QMessageBox()
            msg.setText(
                "There is a problem with the export location's folder structure!"
            )
            msg.setInformativeText(
                "Make sure you are selecting the parent folder that contains"
                "<b>source_data</b> and <b>derived_data</b>."
            )
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Information!")
            msg.exec()
            return

        self._ensure_stopped()
        progress_dialog = ProgressDialog(self, num_rows)
        self.video_progress.connect(progress_dialog.update_queue_label)
        progress_dialog.rejected.connect(self._blurring_cancelled)
        progress_dialog.show()
        logger.info(
            f"Starting video blurring with a threshold of {threshold:.2f}. There are {num_rows} files to process."
        )
        for row in range(num_rows):
            if self._cancel_blurring:
                logger.info(f"Blurring cancelled at start of file {row + 1}.")
                break

            self.video_progress.emit(row)
            QCoreApplication.processEvents()

            # Get paths to location of blurred and unblurred file
            local_path = self._queue.item(row, 0).text()
            new_name = self._queue.item(row, 1).text()
            unblurred_path, blurred_path = self._get_export_path(export_dir, new_name)

            # Copy the original video and change the name
            if not os.path.exists(unblurred_path):
                shutil.copy2(local_path, unblurred_path)

            # Run deface on current video
            commands = [
                "deface",
                local_path,
                "--output",
                blurred_path,
                "--thresh",
                str(threshold),
                "--replacewith",
                "blur",
            ]

            self.blurring_process = subprocess.Popen(commands)
            self.blurring_finished: bool = False
            while not self.blurring_finished:
                # Poll the subprocess and see if it is still running
                retcode = self.blurring_process.poll()
                if retcode is not None:
                    self.blurring_finished = True
                else:
                    QCoreApplication.processEvents()

            if retcode != 0:
                logger.warning(f"Blurring of {new_name} returned error code {retcode}")

            QCoreApplication.processEvents()

        progress_dialog.accept()  # close the progress dialog

    def _set_export_directory(self) -> str:
        dir = QFileDialog.getExistingDirectory(
            parent=self,
            caption="Choose an export location",
            dir=QStandardPaths.writableLocation(QStandardPaths.MoviesLocation),
            options=QFileDialog.ShowDirsOnly,
        )
        return dir

    def _verify_export_directory(self, dir: str) -> bool:
        source_data_folder = os.path.join(dir, "source_data")
        derived_data_folder = os.path.join(dir, "derived_data")
        if os.path.exists(source_data_folder) and os.path.exists(derived_data_folder):
            return True
        return False

    def _get_export_path(
        self, parent_dir: str, blurred_filename: str
    ) -> Tuple[str, str]:
        unblurred_filename = blurred_filename.replace("blur", "unblur")
        tokens = blurred_filename.split(".")[0].split("_")
        subject_folder = f"{tokens[0]}_{tokens[1]}_{tokens[2]}"
        session_folder = f"{tokens[3]}"
        onoff_folder = f"{tokens[4]}"
        unblurred_path = os.path.join(
            parent_dir, "source_data", subject_folder, session_folder, onoff_folder
        )
        if not os.path.exists(unblurred_path):
            os.makedirs(unblurred_path)

        blurred_path = os.path.join(
            parent_dir, "derived_data", subject_folder, session_folder, onoff_folder
        )
        if not os.path.exists(blurred_path):
            os.makedirs(blurred_path)

        return os.path.join(unblurred_path, unblurred_filename), os.path.join(
            blurred_path, blurred_filename
        )

    def _blurring_cancelled(self) -> None:
        if self.blurring_process:
            self.blurring_process.terminate()
        self._cancel_blurring = True

    def _subprocess_finished(self) -> None:
        self._blurring_finished = True


def is_running_from_exe():
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


if __name__ == "__main__":
    VERSION = "2.0.0"

    if is_running_from_exe():
        cwd = sys._MEIPASS
    else:
        cwd = os.path.dirname(os.path.abspath(__file__))

    # Set up logging
    log_folder = os.path.join(cwd, "log")
    if not os.path.exists(log_folder):
        os.mkdir(log_folder)
    now = datetime.now()
    datetime_as_str = now.strftime("%Y-%m-%d_%H%M%S%Z")
    log_file = os.path.join(log_folder, f"{datetime_as_str}.log")
    logging.basicConfig(
        filename=log_file,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )
    sys.stdout = open(log_file, "a")
    sys.stderr = open(log_file, "a")
    logger.info(f"Using blurry version {VERSION}.")

    app = QApplication()
    main_window = MainWindow()
    available_geometry = main_window.screen().availableGeometry()
    main_window.resize(
        available_geometry.width() / 1.5, available_geometry.height() / 1.1
    )
    main_window.show()
    app.exec()
