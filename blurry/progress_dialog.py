# Author: William Liu <liwi@ohsu.edu>

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)


class ProgressDialog(QDialog):
    """A modal dialog to display the progress.

    This dialog, and specificially its own event loop, is where
    the face blurring takes place, not in the main application
    loop.
    """

    def __init__(self, parent, num_videos) -> None:
        super().__init__(parent)

        self.setModal(True)

        self.setWindowTitle("Running blurring...")
        self.button_box = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.button_box.rejected.connect(self.reject)

        self.num_videos_to_blur = num_videos
        self.num_frames = None

        self.queue_progressbar = QProgressBar(parent=self)
        self.queue_progressbar.setMinimum(0)
        self.queue_progressbar.setMaximum(self.num_videos_to_blur)
        self.queue_label = QLabel(parent=self)

        self.frame_progressbar = QProgressBar(parent=self)
        self.frame_progressbar.setMinimum(0)
        self.frame_label = QLabel(parent=self)

        layout = QVBoxLayout()
        layout.addWidget(self.queue_label)
        layout.addWidget(self.queue_progressbar)
        layout.addWidget(self.frame_label)
        layout.addWidget(self.frame_progressbar)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

    @Slot(int)
    def update_queue_progress(self, value) -> None:
        self.queue_progressbar.setValue(value)

    @Slot(int)
    def update_queue_label(self, value) -> None:
        self.queue_label.setText(f"Working on video {value + 1}/{self.num_videos_to_blur}")

    @Slot(int)
    def update_total_frames(self, value) -> None:
        self.frame_progressbar.setMaximum(value)
        self.num_frames = value

    @Slot(int)
    def update_frame_progress(self, value) -> None:
        self.frame_progressbar.setValue(value)

    @Slot(int)
    def update_frame_label(self, value) -> None:
        self.frame_label.setText(f"Working on frame {value}/{self.num_frames}")
