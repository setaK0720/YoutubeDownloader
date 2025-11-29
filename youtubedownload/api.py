"""
FastAPI ベースのWebアプリケーションサーバー
"""
import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List
import json
from pathlib import Path

from downloader import download_manager

# FastAPIアプリケーション
app = FastAPI(
    title="YouTube Downloader",
    description="yt-dlpを使用した動画ダウンローダー",
    version="1.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket接続管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """全接続にメッセージをブロードキャスト"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()


# リクエストモデル
class VideoInfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    quality: str = 'best'  # 'best', '1080', '720', '480', '360'
    audio_only: bool = False
    audio_quality: str = '192'  # '320', '192', '128' (kbps)


# エンドポイント
@app.get("/")
async def read_root():
    """ルートエンドポイント - フロントエンドを返す"""
    try:
        frontend_path = Path(__file__).parent / "frontend" / "index.html"
        
        if not frontend_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {frontend_path}")
        
        return FileResponse(frontend_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/video-info")
async def get_video_info(request: VideoInfoRequest):
    """
    動画情報を取得
    """
    try:
        info = download_manager.get_video_info(request.url)
        return {"success": True, "data": info}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/download")
async def start_download(request: DownloadRequest):
    """
    動画ダウンロードを開始（非同期）
    """
    try:
        # 進捗コールバック
        async def progress_callback(status: dict):
            await manager.broadcast(status)
        
        # バックグラウンドでダウンロードを実行
        async def download_task():
            try:
                # yt_dlpは同期処理なので、executor で実行
                loop = asyncio.get_event_loop()
                
                def sync_download():
                    def sync_callback(status):
                        # 同期コールバックを非同期に変換
                        asyncio.run_coroutine_threadsafe(
                            progress_callback(status), 
                            loop
                        )
                    
                    return download_manager.download_video(
                        request.url,
                        quality=request.quality,
                        audio_only=request.audio_only,
                        audio_quality=request.audio_quality,
                        progress_callback=sync_callback
                    )
                
                result = await loop.run_in_executor(None, sync_download)
                
                # 完了通知
                await manager.broadcast({
                    'download_id': result['id'],
                    'status': 'completed',
                    'result': result
                })
            except Exception as e:
                # エラー通知
                await manager.broadcast({
                    'status': 'error',
                    'error': str(e)
                })
        
        # タスクを開始
        asyncio.create_task(download_task())
        
        return {
            "success": True,
            "message": "ダウンロードを開始しました"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/downloads/{download_id}")
async def get_download_status(download_id: str):
    """
    ダウンロード状態を取得
    """
    status = download_manager.get_download_status(download_id)
    if status:
        return {"success": True, "data": status}
    else:
        raise HTTPException(status_code=404, detail="ダウンロードが見つかりません")


@app.get("/api/downloads/{download_id}/file")
async def download_file(download_id: str):
    """
    ダウンロード済みファイルを配信
    """
    # 履歴から検索
    for item in download_manager.get_history():
        if item.get('id') == download_id:
            filepath = download_manager.get_file_path(item['filename'])
            if filepath:
                return FileResponse(
                    filepath,
                    media_type='video/mp4',
                    filename=item['filename']
                )
    
    raise HTTPException(status_code=404, detail="ファイルが見つかりません")


@app.get("/api/history")
async def get_history():
    """
    ダウンロード履歴を取得
    """
    history = download_manager.get_history()
    return {"success": True, "data": history}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocketエンドポイント - リアルタイム進捗通知
    """
    await manager.connect(websocket)
    try:
        while True:
            # クライアントからのメッセージを待機（キープアライブ）
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# 静的ファイル配信（個別エンドポイント）
@app.get("/styles.css")
async def get_styles():
    css_path = Path(__file__).parent / "frontend" / "styles.css"
    return FileResponse(css_path, media_type="text/css")

@app.get("/app.js")
async def get_app():
    js_path = Path(__file__).parent / "frontend" / "app.js"
    return FileResponse(js_path, media_type="application/javascript")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
