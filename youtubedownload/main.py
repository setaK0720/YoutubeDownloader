import argparse
import sys
import os
import yt_dlp
import static_ffmpeg

static_ffmpeg.add_paths()

def download_video(url):
    """
    指定されたURLから動画をダウンロードする
    """
    # ダウンロード先ディレクトリの作成
    download_dir = "downloads"
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        print(f"ディレクトリを作成しました: {download_dir}")

    ydl_opts = {
        'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
        'format': 'bestvideo+bestaudio/best',  # 最高画質の映像と音声を結合（ffmpeg使用）
        'merge_output_format': 'mp4',  # 結合後のフォーマットをMP4に指定
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"ダウンロードを開始します: {url}")
            ydl.download([url])
            print("ダウンロードが完了しました。")
    except Exception as e:
        print(f"エラーが発生しました: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="YouTube動画ダウンロードツール (yt-dlp使用)")
    parser.add_argument("url", nargs="?", help="ダウンロードしたい動画のURL")
    
    args = parser.parse_args()
    
    url = args.url
    if not url:
        print("URLが指定されていません。")
        try:
            url = input("ダウンロードしたい動画のURLを入力してください: ").strip()
        except KeyboardInterrupt:
            print("\nキャンセルされました。")
            sys.exit(0)
            
    if not url:
        print("URLが入力されませんでした。終了します。")
        sys.exit(1)

    download_video(url)

if __name__ == "__main__":
    main()
