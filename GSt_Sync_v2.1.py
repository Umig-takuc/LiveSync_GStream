import sys
import os
import threading
import tty
import termios
import gi
import configparser

# ---------------------------------------------------------
# 設定ファイル (config.ini) の読み込み
# ---------------------------------------------------------
CONFIG_FILE = "config.ini"

if not os.path.exists(CONFIG_FILE):
    print(f"エラー: 設定ファイル '{CONFIG_FILE}' が見つかりません。")
    print("スクリプトと同じディレクトリに config.ini を作成してください。")
    sys.exit(1)

config = configparser.ConfigParser()
config.read(CONFIG_FILE, encoding='utf-8')

try:
    FILE_PATH = config.get('Settings', 'FILE_PATH')
    UID_1 = config.get('AudioDevices', 'UID_1')
    UID_2 = config.get('AudioDevices', 'UID_2')
except (configparser.NoSectionError, configparser.NoOptionError) as e:
    print(f"エラー: config.ini の必須項目が記述されていません。詳細: {e}")
    sys.exit(1)

# GStreamerの初期化 (Gst.SECONDを使用するため早めに初期化)
gi.require_version('Gst', '1.0')
from gi.repository import Gst
Gst.init(None)

# ---------------------------------------------------------
# シークポイントのパース処理
# ---------------------------------------------------------
def parse_time_to_ns(time_str):
    """ hh:mm:ss:fr (60fps) の文字列をGStreamer用のナノ秒に変換 """
    h, m, s, f = map(int, time_str.split(':'))
    # 1フレーム = 1/60秒 として計算
    total_sec = h * 3600 + m * 60 + s + (f / 60.0)
    return int(total_sec * Gst.SECOND)

seek_points = {}
if config.has_section('SeekPoints'):
    for key, value in config.items('SeekPoints'):
        try:
            # value は '"title01"=00:00:10:00' のような形式を想定
            parts = value.split('=', 1)
            if len(parts) == 2:
                title = parts[0].strip(' "')  # ダブルクォーテーション等を除去
                time_str = parts[1].strip()
                ns_time = parse_time_to_ns(time_str)
                seek_points[key] = {
                    'title': title,
                    'time_str': time_str,
                    'ns': ns_time
                }
        except Exception as e:
            print(f"警告: シークポイント '{key}' の読み込みに失敗しました ({e})")

# --- Appleのネイティブループをインポート ---
try:
    from Cocoa import NSApplication
    from PyObjCTools import AppHelper
    app = NSApplication.sharedApplication()
except ImportError:
    print("エラー: pyobjcがインストールされていません。")
    sys.exit(1)

# ---------------------------------------------------------
# 1. パイプラインの定義
# ---------------------------------------------------------
# ---------------------------------------------------------
# 1. パイプラインの定義 (M3ハードウェア最適化版)
# ---------------------------------------------------------
pipeline_str = f"""
    filesrc location="{FILE_PATH}" ! qtdemux name=demux
    
    demux.video_0 ! queue ! vtdec ! videoconvert ! glimagesink force-aspect-ratio=true sync=true
    demux.video_1 ! queue ! vtdec ! videoconvert ! glimagesink force-aspect-ratio=true sync=true
    
    demux.audio_0 ! queue ! decodebin ! audioconvert ! audioresample ! audiorate ! osxaudiosink unique-id="{UID_1}" sync=true
    demux.audio_1 ! queue ! decodebin ! audioconvert ! audioresample ! audiorate ! osxaudiosink unique-id="{UID_2}" sync=true
"""


try:
    pipeline = Gst.parse_launch(pipeline_str)
except Exception as e:
    print(f"パイプライン構築エラー: {e}")
    sys.exit(1)

is_playing = False

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

def print_status():
    global is_playing
    if is_playing:
        print("\r▶️ 再生中... (一時停止: Space, シーク: S)       ", end="", flush=True)
    else:
        print("\r⏸️ 一時停止中... (再開: Space, シーク: S)       ", end="", flush=True)

def keyboard_listener():
    global is_playing
    print("\n" + "="*40)
    print(" 🎬 コントロールメニュー (macOS Native)")
    print(f" 読み込みファイル: {FILE_PATH}")
    print(" [Space] : 再生開始 / 一時停止")
    print(" [S]     : シークポイントから選択してジャンプ")
    print(" [Q]     : 終了")
    print("="*40 + "\n")
    
    print("\r⏸️ ウィンドウ生成完了。再生待機中... (開始: Space)       ", end="", flush=True)
    
    while True:
        ch = get_single_char().lower()
        
        if ch == ' ':
            if is_playing:
                pipeline.set_state(Gst.State.PAUSED)
                is_playing = False
            else:
                pipeline.set_state(Gst.State.PLAYING)
                is_playing = True
            print_status()
                
        elif ch == 's':
            # シークメニューの表示
            print("\n\n" + "-"*40)
            print(" 📌 シークポイント一覧")
            if not seek_points:
                print("  ※ config.iniに [SeekPoints] が設定されていません。")
            else:
                # キーで並び替えてリスト表示
                for k in sorted(seek_points.keys()):
                    v = seek_points[k]
                    print(f"  [{k}] {v['title']} ({v['time_str']})")
            print("-" * 40)
            
            # 通常の入力モード (input() を使用)
            target_key = input(" シーク先の番号を入力してEnter (キャンセルはそのままEnter): ").strip()
            
            if target_key in seek_points:
                target_ns = seek_points[target_key]['ns']
                print(f"\r⏩ '{seek_points[target_key]['title']}' にジャンプしました！\n")
                pipeline.seek_simple(Gst.Format.TIME, 
                                     Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, 
                                     target_ns)
            else:
                if target_key:
                    print(f"\r⚠️ 番号 '{target_key}' は見つかりません。キャンセルしました。\n")
                else:
                    print("\r⚠️ キャンセルしました。\n")
            
            # 入力完了後、状態表示を復元
            print_status()
            
        elif ch == 'q' or ch == '\x03':
            print("\n\r⏹️ 終了処理中...                    ")
            pipeline.set_state(Gst.State.NULL)
            AppHelper.stopEventLoop()
            break

# ---------------------------------------------------------
# 3. メイン処理の実行
# ---------------------------------------------------------
print("パイプラインを準備中... (ウィンドウを生成しています)")
pipeline.set_state(Gst.State.PAUSED)

input_thread = threading.Thread(target=keyboard_listener)
input_thread.daemon = True
input_thread.start()

AppHelper.runEventLoop()