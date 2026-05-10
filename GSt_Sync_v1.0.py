import sys
import threading
import tty
import termios
import gi

# --- 変更点1: Appleのネイティブループをインポート ---
try:
    from Cocoa import NSApplication
    from PyObjCTools import AppHelper
    app = NSApplication.sharedApplication()
except ImportError:
    print("エラー: pyobjcがインストールされていません。")
    sys.exit(1)

# GStreamerの初期化
gi.require_version('Gst', '1.0')
from gi.repository import Gst

Gst.init(None)

# ---------------------------------------------------------
# 1. パイプラインの定義
# ---------------------------------------------------------
FILE_PATH = "test3.mp4" # ★ 再生したいMP4ファイル
UID_1 = "BuiltInSpeakerDevice" # ★ 音声デバイス1のUID
UID_2 = "BuiltInHeadphoneOutputDevice"   # ★ 音声デバイス2のUID

# ※念のため、videoscaleの後にvideoconvertを追加してフォーマットエラーを防止しています
pipeline_str = f"""
    filesrc location="{FILE_PATH}" ! qtdemux name=demux
    
    demux.video_0 ! queue ! h265parse ! vtdec ! videoconvert ! videoscale ! video/x-raw,pixel-aspect-ratio=1/1 ! videoconvert ! osxvideosink force-aspect-ratio=true
    demux.video_1 ! queue ! h265parse ! vtdec ! videoconvert ! videoscale ! video/x-raw,pixel-aspect-ratio=1/1 ! videoconvert ! osxvideosink force-aspect-ratio=true
    
    demux.audio_0 ! queue ! decodebin ! audioconvert ! audioresample ! osxaudiosink unique-id="{UID_1}"
    demux.audio_1 ! queue ! decodebin ! audioconvert ! audioresample ! osxaudiosink unique-id="{UID_2}"
"""

try:
    pipeline = Gst.parse_launch(pipeline_str)
except Exception as e:
    print(f"パイプライン構築エラー: {e}")
    sys.exit(1)

is_playing = True

# ---------------------------------------------------------
# 2. キーボード入力の監視
# ---------------------------------------------------------
def get_single_char():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def keyboard_listener():
    global is_playing
    print("\n" + "="*40)
    print(" 🎬 コントロールメニュー (macOS Native)")
    print(" [Space] : 一時停止 / 再生")
    print(" [S]     : 30秒目にシーク (スキップ)")
    print(" [Q]     : 終了")
    print("="*40 + "\n")
    
    while True:
        ch = get_single_char().lower()
        
        if ch == ' ':
            if is_playing:
                pipeline.set_state(Gst.State.PAUSED)
                print("\r⏸️ 一時停止中... (再開: Space)       ", end="", flush=True)
                is_playing = False
            else:
                pipeline.set_state(Gst.State.PLAYING)
                print("\r▶️ 再生中... (一時停止: Space)       ", end="", flush=True)
                is_playing = True
                
        elif ch == 's':
            print("\r⏩ 10秒目にジャンプしました！        ", end="", flush=True)
            seek_time = 10 * Gst.SECOND
            pipeline.seek_simple(Gst.Format.TIME, 
                                 Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, 
                                 seek_time)
            
        elif ch == 'q' or ch == '\x03':
            print("\r⏹️ 終了処理中...                    ")
            pipeline.set_state(Gst.State.NULL)
            # --- 変更点2: Appleのループを停止 ---
            AppHelper.stopEventLoop()
            break

# ---------------------------------------------------------
# 3. メイン処理の実行
# ---------------------------------------------------------
pipeline.set_state(Gst.State.PLAYING)

input_thread = threading.Thread(target=keyboard_listener)
input_thread.daemon = True
input_thread.start()

# --- 変更点3: GLibの代わりにAppleのイベントループを回す ---
print("ウィンドウを初期化中...")
AppHelper.runEventLoop()