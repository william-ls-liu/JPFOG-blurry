# Author: William Liu <liwi@ohsu.edu>

import av


class Encoder:
    """Object that handles video encoding.

    Parameters
    ----------
    output : str
        Full path where video will be saved.
    frames : array_like
        Array of individual frames of the video.
    fps : float
        Frames per second of output video.
    bitrate : int
        Bitrate in kbps.
    width : int
        Width of resulting video, in pixels.
    height : int
        Height of resulting video, in pixels.
    codec : str, optional
        Codec using to encode video, default is h264.
    """

    def __init__(self, output, fps, bitrate, width, height, codec="h264") -> None:
        # Open the video file to stream data
        self.video_out = av.open(output, mode="w")
        self.stream = self.video_out.add_stream(
            codec, rate=fps, options={"x265-params": "log_level=none"}
        )
        self.stream.codec_context.bit_rate = bitrate
        self.stream.height = height
        self.stream.width = width

    def encode_frame(self, frame) -> None:
        to_encode = av.VideoFrame.from_ndarray(frame)
        for packet in self.stream.encode(to_encode):
            self.video_out.mux(packet)

    def finish(self) -> None:
        # Flush the output stream
        for packet in self.stream.encode(None):
            self.video_out.mux(packet)
        self.video_out.close()


class Decoder:
    """Object that decodes a video file.

    Parameters
    ----------
    path : str
        Path to the video file to decode.
    """

    def __init__(self, path) -> None:
        self.video_in = av.open(path)
        self.stream = self.video_in.streams.video[0]
        self.bit_rate = self.stream.codec_context.bit_rate
        self.height = self.stream.height
        self.width = self.stream.width
        self.fps = self.stream.average_rate
        self.frames = self.stream.frames
        self.codec = self.stream.codec_context.name

    def decode(self) -> None:
        return self.video_in.decode(video=0)

    def finish(self) -> None:
        self.video_in.close()
