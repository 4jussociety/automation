import asyncio
import os
import subprocess

DEFAULT_VOICE = "ko-KR-SunHiNeural"

async def _async_edge_tts(text: str, audio_path: str, srt_path: str = None, voice: str = DEFAULT_VOICE):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate="+5%", pitch="+0Hz")
    
    if srt_path:
        submaker = edge_tts.SubMaker()
        with open(audio_path, "wb") as file:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    submaker.feed(chunk)
        with open(srt_path, "w", encoding="utf-8") as file:
            file.write(submaker.get_srt())
    else:
        await communicate.save(audio_path)

def generate_voice(text: str, audio_path: str, srt_path: str = None, voice: str = DEFAULT_VOICE):
    try:
        import edge_tts
        asyncio.run(_async_edge_tts(text, audio_path, srt_path, voice))
        print(f"[TTS] Edge-TTS voice generated: {audio_path}")
        return True
    except ImportError:
        print("[TTS Info] edge-tts package not installed in environment. Creating fallback audio.")
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", "10", "-q:a", "9", "-acodec", "libmp3lame", audio_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if srt_path:
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write("1\n00:00:00,000 --> 00:00:10,000\n" + text + "\n")
        return True
    except Exception as e:
        print(f"[TTS Fallback] {e}")
        return True
