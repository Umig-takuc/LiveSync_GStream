# LiveSync_GStream
GStreamを使用したライブ用マルチストリームmp4再生用pythonスクリプト。
Mac版であるがWindows版もあとで作成する予定。
LiveSync_OBSのようなWebサーバーを用いた管理機能も実装したい

## (Usage)
- 事前に必要な動画ストリームを **ffmpeg** を用いてmulti-stream mp4ファイルにしておくこと。詳細は追記予定。
- `gst-device-monitor-1.0 Audio/Sink` コマンドにより音声デバイスのUniqueIDをconfigファイルに記述すること
- 現時点でmp4/HEVC 2v2aストリームを想定

## (注意事項)
- 再生ファイルは音声コーデックがaacの場合、その仕様上最初の再生時にスピーカー間（stream間）で音ズレが発生し、シークを一度かける必要がある。したがって音声コーデックは **pcm_s16le** を推奨する
- なお現時点では動画ファイルのコーデックはHEVCのみを想定している
- アクティブスピーカーやテレビなどのデバイスでは機器内部の回路により遅延が発生するようなので、バッチリ合わない可能性があります


## (version history)

### 1.0-r2
- config.iniに設定を外部化。
- シークタイムリストを実装済み。

### 1.0
- initial version
