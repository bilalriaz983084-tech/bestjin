from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import requests
import re
import os
import time

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Railway Media Extractor (Robust yt-dlp + Invidious)",
        "engine": "yt-dlp"
    })

def extract_youtube_id(url):
    clean = (url or '').strip()
    match = re.search(r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=|shorts\/)|youtu\.be\/)([^"&?/\s]{11})', clean)
    return match.group(1) if match else None

# =========================================================================
# 🌟 YouTube Downloader (Dual Engine: yt-dlp + Invidious Fallback)
# =========================================================================
@app.route('/api/youtube/download', methods=['POST'])
def youtube_download():
    data = request.get_json(silent=True) or {}
    raw_url = data.get('url') or data.get('link') or request.args.get('url')
    format_type = (data.get('formatType') or 'video').lower()
    is_audio = format_type == 'audio'

    if not raw_url:
        return jsonify({"success": False, "error": "YouTube URL is required"}), 400

    video_id = extract_youtube_id(raw_url)
    if not video_id:
        return jsonify({"success": False, "error": "Invalid YouTube URL"}), 400

    target_url = f"https://www.youtube.com/watch?v={video_id}"
    default_thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    stream_url = None
    video_title = f"YouTube_{video_id}"

    # LAYER 1: yt-dlp Engine
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'format': 'bestaudio/best' if is_audio else 'best[ext=mp4]/best',
        'socket_timeout': 15,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)
            video_title = info.get('title', video_title)
            stream_url = info.get('url')
            if not stream_url and 'formats' in info:
                formats = info['formats']
                if is_audio:
                    chosen = next((f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none'), formats[-1])
                else:
                    chosen = next((f for f in formats if f.get('ext') == 'mp4' and f.get('acodec') != 'none'), formats[-1])
                stream_url = chosen.get('url')
    except Exception:
        pass

    # LAYER 2: Invidious Open Nodes Fallback (Agar yt-dlp block ho jaye)
    if not stream_url:
        invidious_nodes = [
            'https://inv.nadeko.net',
            'https://invidious.nerdvpn.de',
            'https://yt.artemislena.eu'
        ]
        for node in invidious_nodes:
            try:
                res = requests.get(f"{node}/api/v1/videos/{video_id}", timeout=4)
                if res.status_code == 200:
                    j = res.json()
                    video_title = j.get('title', video_title)
                    if is_audio and 'adaptiveFormats' in j:
                        aud = next((a for a in j['adaptiveFormats'] if 'audio/mp4' in a.get('type', '')), None)
                        if aud and 'url' in aud:
                            stream_url = aud['url']
                            break
                    elif not is_audio and 'formatStreams' in j:
                        vid = next((s for s in j['formatStreams'] if s.get('container') == 'mp4'), None)
                        if vid and 'url' in vid:
                            stream_url = vid['url']
                            break
            except Exception:
                continue

    if stream_url:
        return jsonify({
            "success": True,
            "type": "audio" if is_audio else "video",
            "title": video_title,
            "thumbnail": default_thumb,
            "downloadUrl": stream_url,
            "formats": [{
                "quality": "Audio Only (MP3)" if is_audio else "HD Video (MP4)",
                "downloadUrl": stream_url,
                "extension": "mp3" if is_audio else "mp4",
                "type": "audio" if is_audio else "video"
            }]
        })

    return jsonify({"success": False, "error": "YouTube stream could not be extracted. Video might be private or restricted."}), 400

# =========================================================================
# 🌟 Facebook Downloader Route
# =========================================================================
@app.route('/api/facebook/download', methods=['POST'])
def facebook_download():
    data = request.get_json(silent=True) or {}
    raw_url = data.get('url') or data.get('link') or request.args.get('url')

    if not raw_url:
        return jsonify({"success": False, "error": "Facebook URL is required"}), 400

    clean_url = raw_url.strip()
    id_match = re.search(r'(?:v=|videos/|reel/)(\d+)', clean_url)
    target_url = f"https://www.facebook.com/watch/?v={id_match.group(1)}" if id_match else clean_url

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'format': 'best[ext=mp4]/best',
        'socket_timeout': 20,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)

        title = info.get('title') or f"Facebook_Video_{int(time.time())}"
        thumbnail = info.get('thumbnail') or ''
        stream_url = info.get('url')

        if not stream_url and 'formats' in info:
            chosen = next((f for f in info['formats'] if f.get('ext') == 'mp4'), info['formats'][-1])
            stream_url = chosen.get('url')

        if stream_url:
            return jsonify({
                "success": True,
                "type": "video",
                "title": title,
                "thumbnail": thumbnail or stream_url,
                "downloadUrl": stream_url,
                "formats": [{
                    "quality": "HD Video (MP4)",
                    "downloadUrl": stream_url,
                    "extension": "mp4",
                    "type": "video"
                }]
            })

        return jsonify({"success": False, "error": "Facebook video stream could not be extracted"}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
