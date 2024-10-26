import asyncio
from frameutils import Bluetooth
import sounddevice as sd
import numpy as np
import speech_recognition as sr

audio_buffer = b""
recognizer = sr.Recognizer()


def receive_data(data):
    global audio_buffer
    audio_buffer += data


async def record_and_transcribe(b: Bluetooth, sample_rate, bit_depth):
    global audio_buffer
    audio_buffer = b""

    # Start the microphone on the Frame glasses
    await b.send_lua(
        f"frame.microphone.start{{sample_rate={sample_rate}, bit_depth={bit_depth}}}"
    )

    # Continuously read microphone data
    await b.send_lua(
        f"while true do s=frame.microphone.read({b.max_data_payload()}); if s==nil then break end if s~='' then while true do if (pcall(frame.bluetooth.send,s)) then break end end end end"
    )

    # Collect audio for a fixed time interval
    await asyncio.sleep(5)

    # Stop the microphone
    await b.send_break_signal()
    await b.send_lua("frame.microphone.stop()")

    # Convert the received audio data
    if bit_depth == 16:
        audio_data = np.frombuffer(audio_buffer, dtype=np.int16)
    elif bit_depth == 8:
        audio_data = np.frombuffer(audio_buffer, dtype=np.int8)

    # Convert to float32 and normalize
    audio_data = audio_data.astype(np.float32)
    if bit_depth == 16:
        audio_data /= np.iinfo(np.int16).max
    elif bit_depth == 8:
        audio_data /= np.iinfo(np.int8).max

    # Convert NumPy array to audio bytes for recognition
    audio_float32 = (audio_data * 32767).astype(np.int16).tobytes()
    audio_sample = sr.AudioData(audio_float32, sample_rate, 2 if bit_depth == 16 else 1)

    # Recognize speech using the recognizer
    try:
        transcription = recognizer.recognize_google(audio_sample)
        print(f"Transcription: {transcription}")
        # Send transcription to Frame for display
        await b.send_lua(f'frame.display.clear()')
        await b.send_lua(f'frame.display.text("{transcription}", 10, 10)')
        await b.send_lua("frame.display.show()")

    except sr.UnknownValueError:
        print("Speech was unclear.")
        await b.send_lua(f'frame.display.clear()')
        await b.send_lua(f'frame.display.text("...listening...", 10, 10)')
        await b.send_lua("frame.display.show()")

    except sr.RequestError:
        print("Could not request results from the speech recognition service.")


async def main():
    b = Bluetooth()

    # Connect and start streaming with different bit depths and sample rates
    await b.connect(data_response_handler=receive_data)
    await record_and_transcribe(b, 8000, 8)
    await record_and_transcribe(b, 8000, 16)
    await record_and_transcribe(b, 16000, 8)
    await b.disconnect()


asyncio.run(main())
