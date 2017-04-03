import numpy as np
from pyaudio import PyAudio
# sudo apt-get install python-pyaudio

BITRATE = 16000  # number of frames per second/frameset.


def sine(frequency=1000, duration=1):
    """ plays a sine tone for duration on the PC speaker """
    frequency, duration = float(frequency), float(duration)
    NUMBEROFFRAMES = int(BITRATE * LENGTH)
    RESTFRAMES = NUMBEROFFRAMES % BITRATE
    WAVEDATA = ''

    for x in xrange(NUMBEROFFRAMES):
        WAVEDATA = WAVEDATA + chr(
            int(math.sin(x / ((BITRATE / FREQUENCY) / math.pi)) * 127 + 128))

        # fill remainder of frameset with silence
    for x in xrange(RESTFRAMES):
        WAVEDATA = WAVEDATA + chr(128)

    p = PyAudio()
    stream = p.open(format=p.get_format_from_width(1),
                    channels=1,
                    rate=BITRATE,
                    output=True)
    stream.write(WAVEDATA)
    stream.stop_stream()
    stream.close()
    p.terminate()
