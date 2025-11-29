"""
YouTube動画ダウンローダーのコアモジュール
"""
import os
import json
import uuid
from datetime import datetime
from typing import Dict, Optional, Callable
from pathlib import Path
import yt_dlp
import static_ffmpeg

# ffmpegのパスを追加
static_ffmpeg.add_paths()

# ダウンロードディレクトリ
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# 履歴ファイル
HISTORY_FILE = Path("download_history.json")


class DownloadManager:
    """ダウンロード管理クラス"""
    
    def __init__(self):
        self.active_downloads: Dict[str, Dict] = {}
        self.history = self._load_history()
    
    def _load_history(self) -> list:
        """履歴ファイルから読み込み"""
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []
    
    def _save_history(self):
        """履歴ファイルに保存"""
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"履歴の保存に失敗: {e}")
    
    def get_video_info(self, url: str) -> Dict:
        """
        動画情報を取得
        
        Args:
            url: 動画のURL
            
        Returns:
            動画情報の辞書
        """
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                return {
                    'title': info.get('title', 'Unknown Title'),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'description': info.get('description', '')[:200],  # 最初の200文字のみ
                    'view_count': info.get('view_count', 0),
                }
        except Exception as e:
            raise Exception(f"動画情報の取得に失敗しました: {str(e)}")
    
    def download_video(
        self, 
        url: str, 
        quality: str = 'best',
        audio_only: bool = False,
        audio_quality: str = '192',
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """
        動画をダウンロード
        
        Args:
            url: 動画のURL
            quality: 動画品質 ('best', '1080', '720', '480', '360')
            audio_only: 音声のみダウンロードするか
            audio_quality: 音声品質 ('320', '192', '128') kbps
            progress_callback: 進捗コールバック関数
            
        Returns:
            ダウンロード情報の辞書
        """
        download_id = str(uuid.uuid4())
        
        # 進捗フック
        def progress_hook(d):
            if progress_callback:
                status = {
                    'download_id': download_id,
                    'status': d['status'],
                }
                
                if d['status'] == 'downloading':
                    # ダウンロード中
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    speed = d.get('speed', 0)
                    eta = d.get('eta', 0)
                    
                    status.update({
                        'progress': (downloaded / total * 100) if total > 0 else 0,
                        'downloaded_bytes': downloaded,
                        'total_bytes': total,
                        'speed': speed,
                        'eta': eta,
                    })
                elif d['status'] == 'finished':
                    # ダウンロード完了（処理中）
                    status['progress'] = 100
                    status['message'] = 'ファイルを処理中...'
                
                progress_callback(status)
        
        # フォーマット選択
        if audio_only:
            # 音声のみダウンロード
            format_str = 'bestaudio/best'
            output_ext = 'mp3'
            postprocessors = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': audio_quality,
            }]
        else:
            # 動画ダウンロード
            if quality == 'best':
                format_str = 'bestvideo+bestaudio/best'
            else:
                # 指定解像度
                format_str = f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]'
            output_ext = 'mp4'
            postprocessors = []
        
        ydl_opts = {
            'outtmpl': str(DOWNLOAD_DIR / '%(title)s.%(ext)s'),
            'format': format_str,
            'merge_output_format': output_ext if not audio_only else None,
            'noplaylist': True,
            'progress_hooks': [progress_hook],
            'postprocessors': postprocessors,
        }
        
        try:
            # ダウンロード開始
            self.active_downloads[download_id] = {
                'id': download_id,
                'url': url,
                'status': 'downloading',
                'progress': 0,
                'started_at': datetime.now().isoformat(),
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # ダウンロードされたファイルのパスを取得
                filename = ydl.prepare_filename(info)
                
                # 拡張子を調整
                if audio_only:
                    # 音声のみの場合、mp3に変更
                    base = os.path.splitext(filename)[0]
                    filename = base + '.mp3'
                else:
                    # 動画の場合、mp4に変更（merge後）
                    if not filename.endswith('.mp4'):
                        base = os.path.splitext(filename)[0]
                        filename = base + '.mp4'
                
                # ダウンロード完了
                result = {
                    'id': download_id,
                    'status': 'completed',
                    'title': info.get('title', 'Unknown Title'),
                    'filename': os.path.basename(filename),
                    'filepath': filename,
                    'thumbnail': info.get('thumbnail', ''),
                    'format_type': 'audio' if audio_only else 'video',
                    'quality': quality,
                    'completed_at': datetime.now().isoformat(),
                }
                
                # 履歴に追加
                self.history.insert(0, result)  # 最新を先頭に
                self._save_history()
                
                # アクティブダウンロードから削除
                if download_id in self.active_downloads:
                    del self.active_downloads[download_id]
                
                return result
                
        except Exception as e:
            # エラー時
            error_result = {
                'id': download_id,
                'status': 'error',
                'error': str(e),
                'completed_at': datetime.now().isoformat(),
            }
            
            if download_id in self.active_downloads:
                del self.active_downloads[download_id]
            
            raise Exception(f"ダウンロードに失敗しました: {str(e)}")
    
    def get_download_status(self, download_id: str) -> Optional[Dict]:
        """ダウンロード状態を取得"""
        return self.active_downloads.get(download_id)
    
    def get_history(self, limit: int = 50) -> list:
        """履歴を取得"""
        return self.history[:limit]
    
    def get_file_path(self, filename: str) -> Optional[Path]:
        """ファイルパスを取得"""
        filepath = DOWNLOAD_DIR / filename
        if filepath.exists():
            return filepath
        return None


# グローバルインスタンス
download_manager = DownloadManager()
