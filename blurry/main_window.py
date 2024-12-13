# Author: William Liu <liwi@ohsu.edu>

import os
import shutil
import sys

import av
import av.logging
import cv2 as cv
import skimage.draw
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
from video import Decoder, Encoder

from centerface import CenterFace


class MainWindow(QMainWindow):
    """The Main Window of the application."""

    video_progress = Signal(int)
    frame_progress = Signal(int)
    total_frames = Signal(int)

    def __init__(self, model_path) -> None:
        super().__init__()

        self._model_path = model_path

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
        self._threshold_spinbox.setValue(0.35)
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
        event.accept()

    @Slot()
    def open_video(self):
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
            self._media_player.play()
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
        if not self._verify_unique_filename(new_filename):
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
        new_name = QTableWidgetItem(new_filename)
        new_name.setFlags(~Qt.ItemIsEditable)
        delete_button = QPushButton("Remove", parent=self._queue)
        delete_button.clicked.connect(self.remove_row)
        num_rows = self._queue.rowCount()
        # Create a custom property so each button knows what row to operate on
        delete_button.setProperty("Row", num_rows)
        self._queue.setRowCount(num_rows + 1)
        self._queue.setItem(num_rows, 0, original_name)
        self._queue.setItem(num_rows, 1, new_name)
        self._queue.setCellWidget(num_rows, 2, delete_button)

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
            return f"{site_id}sub{subject_id:03d}_{freezer_status}_{session_id}_{medication_status}_{trial_id}_{video_plane}_blur.mp4"

        return f"{site_id}sub{subject_id:03d}_{freezer_status}_{session_id}_{medication_status}_{trial_id}-retr{retry}_{video_plane}_blur.mp4"

    def _verify_unique_filename(self, prop: str) -> bool:
        for row in range(self._queue.rowCount()):
            name = self._queue.item(row, 1).text()
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
            return

        blur_export_dir = os.path.join(export_dir, "blur")
        unblur_export_dir = os.path.join(export_dir, "unblur")
        try:
            os.mkdir(blur_export_dir)
            os.mkdir(unblur_export_dir)
        except FileExistsError:
            pass

        self._ensure_stopped()
        centerface = CenterFace(self._model_path)
        progress_dialog = ProgressDialog(self, num_rows)
        self.video_progress.connect(progress_dialog.update_queue_progress)
        self.video_progress.connect(progress_dialog.update_queue_label)
        self.frame_progress.connect(progress_dialog.update_frame_progress)
        self.frame_progress.connect(progress_dialog.update_frame_label)
        self.total_frames.connect(progress_dialog.update_total_frames)
        progress_dialog.rejected.connect(self._blurring_cancelled)
        progress_dialog.show()
        for row in range(num_rows):
            if self._cancel_blurring:
                break

            self.video_progress.emit(row)
            QCoreApplication.processEvents()
            local_path = self._queue.item(row, 0).text()
            new_name = self._queue.item(row, 1).text()
            unblurred_new_name = new_name.replace("blur", "unblur")
            shutil.copy2(
                local_path, os.path.join(unblur_export_dir, unblurred_new_name)
            )
            new_path = os.path.join(blur_export_dir, new_name)
            decoder = Decoder(local_path)
            encoder = Encoder(
                new_path,
                decoder.fps,
                decoder.bit_rate // 2,
                decoder.width,
                decoder.height,
                decoder.codec,
            )
            self.total_frames.emit(decoder.frames)
            for i, frame in enumerate(decoder.decode()):
                if self._cancel_blurring:
                    break

                self.frame_progress.emit(i + 1)
                QCoreApplication.processEvents()
                img_as_array = frame.to_ndarray(format="rgb24")
                dets, _ = centerface(img_as_array, frame.height, frame.width, threshold)
                QCoreApplication.processEvents()  # the detection operation takes the longest, so process events on either side of it
                for det in dets:
                    boxes, _ = det[:4], det[4]
                    x1, y1, x2, y2 = boxes.astype(int)
                    h, w = y2 - y1, x2 - x1
                    scale = 0.3
                    bf = 2
                    y1 -= int(h * scale)
                    y2 += int(h * scale)
                    x1 -= int(w * scale)
                    x2 += int(w * scale)
                    y1, y2 = max(0, y1), min(img_as_array.shape[0] - 1, y2)
                    x1, x2 = max(0, x1), min(img_as_array.shape[1] - 1, x2)
                    face_roi = img_as_array[y1:y2, x1:x2]
                    blurred_box = cv.blur(
                        img_as_array[y1:y2, x1:x2],
                        (abs(x2 - x1) // bf, abs(y2 - y1) // bf),
                    )
                    ey, ex = skimage.draw.ellipse(
                        (y2 - y1) // 2, (x2 - x1) // 2, (y2 - y1) // 2, (x2 - x1) // 2
                    )
                    face_roi[ey, ex] = blurred_box[ey, ex]
                    img_as_array[y1:y2, x1:x2] = face_roi
                encoder.encode_frame(img_as_array)
            encoder.finish()
            decoder.finish()
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

    def _blurring_cancelled(self) -> None:
        self._cancel_blurring = True


def is_running_from_exe():
    return getattr(sys, "frozen", False)


if __name__ == "__main__":
    if is_running_from_exe():
        base_path = sys._MEIPASS
        model_path = os.path.join(base_path, "models/centerface_bnmerged.onnx")
    else:
        base_path = os.path.dirname(__file__)
        model_path = os.path.join(base_path, "../models/centerface_bnmerged.onnx")

    av.logging.set_level(av.logging.PANIC)
    app = QApplication()
    main_window = MainWindow(model_path)
    available_geometry = main_window.screen().availableGeometry()
    main_window.resize(
        available_geometry.width() / 1.5, available_geometry.height() / 1.1
    )
    main_window.show()
    app.exec()
