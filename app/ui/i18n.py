"""介面字串表：繁中／簡中／英文。

只涵蓋 GUI 字串；worker 的 stderr 訊息維持繁中（技術日誌，使用者不需讀懂）。
"""
from __future__ import annotations

from PySide6.QtCore import QLocale

LANGS = ("zh_TW", "zh_CN", "en")
DEFAULT = "zh_TW"

_STRINGS: dict[str, dict[str, str]] = {
    "app.title": {
        "zh_TW": "影片畫質增強", "zh_CN": "视频画质增强", "en": "Video Enhancer"},
    "drop.hint": {
        "zh_TW": "把影片拖進來", "zh_CN": "把视频拖进来", "en": "Drop a video here"},
    "drop.loaded": {
        "zh_TW": "{name}\n{width}×{height}  {fps:.2f}fps  {duration:.1f}s",
        "zh_CN": "{name}\n{width}×{height}  {fps:.2f}fps  {duration:.1f}s",
        "en": "{name}\n{width}×{height}  {fps:.2f}fps  {duration:.1f}s"},
    "btn.pick": {
        "zh_TW": "選擇影片", "zh_CN": "选择视频", "en": "Choose video"},
    "btn.start": {"zh_TW": "開始", "zh_CN": "开始", "en": "Start"},
    "btn.stop": {"zh_TW": "中止", "zh_CN": "中止", "en": "Stop"},
    "card.settings": {
        "zh_TW": "輸出設定", "zh_CN": "输出设置", "en": "Output settings"},
    "card.progress": {"zh_TW": "進度", "zh_CN": "进度", "en": "Progress"},
    "card.log": {"zh_TW": "日誌", "zh_CN": "日志", "en": "Log"},
    "chk.sr": {"zh_TW": "超分到 4K", "zh_CN": "超分到 4K", "en": "Upscale to 4K"},
    "chk.fi": {"zh_TW": "補幀", "zh_CN": "补帧", "en": "Interpolate frames"},
    "lbl.content": {
        "zh_TW": "素材類型", "zh_CN": "素材类型", "en": "Content"},
    "lbl.quality": {"zh_TW": "畫質", "zh_CN": "画质", "en": "Quality"},
    "lbl.fps": {"zh_TW": "補幀目標", "zh_CN": "补帧目标", "en": "Target fps"},
    "lbl.profile": {"zh_TW": "編碼", "zh_CN": "编码", "en": "Encoding"},
    "lbl.title": {"zh_TW": "主題", "zh_CN": "主题", "en": "Title"},
    "lbl.subtitle": {"zh_TW": "副題", "zh_CN": "副题", "en": "Subtitle"},
    "lbl.outdir": {
        "zh_TW": "輸出目錄", "zh_CN": "输出目录", "en": "Output folder"},
    "content.live": {"zh_TW": "實拍", "zh_CN": "实拍", "en": "Live action"},
    "content.anime": {"zh_TW": "動畫", "zh_CN": "动画", "en": "Animation"},
    "quality.fast": {"zh_TW": "快", "zh_CN": "快", "en": "Fast"},
    "quality.standard": {"zh_TW": "標準", "zh_CN": "标准", "en": "Standard"},
    "quality.best": {"zh_TW": "最佳", "zh_CN": "最佳", "en": "Best"},
    "fps.60": {"zh_TW": "60 fps", "zh_CN": "60 fps", "en": "60 fps"},
    "fps.120": {
        "zh_TW": "120 fps（檔案約翻倍）",
        "zh_CN": "120 fps（文件约翻倍）",
        "en": "120 fps (file roughly doubles)"},
    "profile.standard": {
        "zh_TW": "標準", "zh_CN": "标准", "en": "Standard"},
    "profile.fast": {"zh_TW": "快速", "zh_CN": "快速", "en": "Fast"},
    "profile.small": {
        "zh_TW": "小檔案（慢 4 倍）",
        "zh_CN": "小文件（慢 4 倍）",
        "en": "Small file (4× slower)"},
    "hint.fast_live": {
        "zh_TW": "速度最快，適合先試看效果",
        "zh_CN": "速度最快，适合先试看效果",
        "en": "Fastest — good for a quick trial"},
    "hint.standard_live": {
        "zh_TW": "畫質與速度平衡，1080p 素材的最佳選擇",
        "zh_CN": "画质与速度平衡，1080p 素材的最佳选择",
        "en": "Balanced — the best choice for 1080p footage"},
    "hint.best_live": {
        "zh_TW": "細節最多，速度約慢 3 倍",
        "zh_CN": "细节最多，速度约慢 3 倍",
        "en": "Most detail — about 3× slower"},
    "hint.fast_anime": {
        "zh_TW": "線條乾淨，速度最快",
        "zh_CN": "线条干净，速度最快",
        "en": "Clean lines, fastest"},
    "hint.best_anime": {
        "zh_TW": "線條最銳利，速度約慢 2 倍",
        "zh_CN": "线条最锐利，速度约慢 2 倍",
        "en": "Sharpest lines — about 2× slower"},
    "hint.no_sr": {
        "zh_TW": "不超分，輸出維持原解析度",
        "zh_CN": "不超分，输出保持原分辨率",
        "en": "No upscaling — output keeps source resolution"},
    "hint.no_fi": {
        "zh_TW": "不補幀，維持原幀率",
        "zh_CN": "不补帧，保持原帧率",
        "en": "No interpolation — source frame rate kept"},
    "hint.fi_skip": {
        "zh_TW": "來源已 {fps:.2f}fps，未達 {target}fps，補幀會略過",
        "zh_CN": "来源已 {fps:.2f}fps，未达 {target}fps，补帧会跳过",
        "en": "Source is {fps:.2f}fps — interpolation skipped"},
    "hint.sep": {"zh_TW": "　·　", "zh_CN": "　·　", "en": "  ·  "},
    "status.idle": {"zh_TW": "待機", "zh_CN": "待机", "en": "Idle"},
    "status.starting": {
        "zh_TW": "啟動中…", "zh_CN": "启动中…", "en": "Starting…"},
    "status.done": {
        "zh_TW": "完成，耗時 {seconds:.1f} 秒",
        "zh_CN": "完成，耗时 {seconds:.1f} 秒",
        "en": "Done in {seconds:.1f}s"},
    "status.rejected": {
        "zh_TW": "已拒絕：素材不符合條件",
        "zh_CN": "已拒绝：素材不符合条件",
        "en": "Rejected — unsupported source"},
    "status.failed": {
        "zh_TW": "失敗（退出碼 {code}）",
        "zh_CN": "失败（退出码 {code}）",
        "en": "Failed (exit code {code})"},
    "log.read_fail": {
        "zh_TW": "讀取資訊失敗：{error}",
        "zh_CN": "读取信息失败：{error}",
        "en": "Could not read video info: {error}"},
    "log.aborted": {
        "zh_TW": "使用者中止", "zh_CN": "用户中止", "en": "Stopped by user"},
    "log.output": {
        "zh_TW": "輸出：{path}", "zh_CN": "输出：{path}", "en": "Output: {path}"},
    "msg.no_input.title": {
        "zh_TW": "缺少輸入", "zh_CN": "缺少输入", "en": "No video selected"},
    "msg.no_input.body": {
        "zh_TW": "先選一段影片。",
        "zh_CN": "先选一段视频。",
        "en": "Pick a video first."},
    "msg.output_exists.title": {
        "zh_TW": "輸出檔已存在", "zh_CN": "输出文件已存在", "en": "Output file already exists"},
    "msg.output_exists.body": {
        "zh_TW": "請更改輸出檔名或資料夾。\n{path}",
        "zh_CN": "请更改输出文件名或文件夹。\n{path}",
        "en": "Choose a different output name or folder.\n{path}"},
    "dlg.pick_video": {
        "zh_TW": "選擇影片", "zh_CN": "选择视频", "en": "Choose video"},
    "dlg.pick_outdir": {
        "zh_TW": "選擇輸出目錄",
        "zh_CN": "选择输出目录",
        "en": "Choose output folder"},
    "dlg.video_filter": {
        "zh_TW": "影片 (*.mp4 *.mov *.mkv *.avi *.m4v *.wmv)",
        "zh_CN": "视频 (*.mp4 *.mov *.mkv *.avi *.m4v *.wmv)",
        "en": "Videos (*.mp4 *.mov *.mkv *.avi *.m4v *.wmv)"},
    "tip.min": {"zh_TW": "最小化", "zh_CN": "最小化", "en": "Minimize"},
    "tip.max": {"zh_TW": "最大化", "zh_CN": "最大化", "en": "Maximize"},
    "tip.close": {"zh_TW": "關閉", "zh_CN": "关闭", "en": "Close"},
    "btn.browse": {"zh_TW": "…", "zh_CN": "…", "en": "…"},
    "outdir.default_name": {
        "zh_TW": "影片畫質增強", "zh_CN": "视频画质增强", "en": "VideoEnhancer"},

    # 首啟精靈
    "wizard.title": {
        "zh_TW": "初次設定", "zh_CN": "初次设置", "en": "First-time setup"},
    "wizard.step": {
        "zh_TW": "步驟 {current} / {total}",
        "zh_CN": "步骤 {current} / {total}",
        "en": "Step {current} of {total}"},
    "wizard.scan.title": {
        "zh_TW": "檢查你的裝置", "zh_CN": "检查你的设备", "en": "Checking your device"},
    "wizard.scan.gpu": {
        "zh_TW": "顯示卡", "zh_CN": "显卡", "en": "Graphics card"},
    "wizard.scan.vram": {
        "zh_TW": "顯示記憶體", "zh_CN": "显存", "en": "Video memory"},
    "wizard.scan.cpu": {
        "zh_TW": "處理器核心", "zh_CN": "处理器核心", "en": "CPU cores"},
    "wizard.scan.ram": {
        "zh_TW": "記憶體", "zh_CN": "内存", "en": "Memory"},
    "wizard.scan.disk": {
        "zh_TW": "可用磁碟空間", "zh_CN": "可用磁盘空间", "en": "Free disk space"},
    "wizard.scan.ffmpeg": {
        "zh_TW": "轉檔工具", "zh_CN": "转码工具", "en": "Video encoder"},
    "wizard.scan.not_found": {
        "zh_TW": "找不到", "zh_CN": "找不到", "en": "Not found"},
    "wizard.scan.tile": {
        "zh_TW": "依顯存自動選用分塊大小：{tile} px",
        "zh_CN": "依显存自动选用分块大小：{tile} px",
        "en": "Tile size picked from video memory: {tile} px"},
    "wizard.tools_missing": {
        "zh_TW": "無法執行 ffmpeg 或 ffprobe，請重新安裝程式，或將兩者加入 PATH。",
        "zh_CN": "无法运行 ffmpeg 或 ffprobe，请重新安装程序，或将两者加入 PATH。",
        "en": "Could not run ffmpeg or ffprobe. Reinstall the app or add both tools to PATH."},
    "wizard.unsupported.title": {
        "zh_TW": "需要獨立顯卡", "zh_CN": "需要独立显卡", "en": "A dedicated GPU is required"},
    "wizard.unsupported.body": {
        "zh_TW": "這套軟體需要 NVIDIA 或 AMD 獨立顯卡才能加速處理。目前偵測不到，程式無法繼續。",
        "zh_CN": "这套软件需要 NVIDIA 或 AMD 独立显卡才能加速处理。目前检测不到，程序无法继续。",
        "en": "This app needs an NVIDIA or AMD dedicated GPU. None was detected, so setup cannot continue."},
    "wizard.models.title": {
        "zh_TW": "選擇要安裝的模型", "zh_CN": "选择要安装的模型", "en": "Choose models to install"},
    "wizard.models.hint": {
        "zh_TW": "已全部勾選。模型決定畫質，第一次都需要下載；之後就不會再下載。",
        "zh_CN": "已全部勾选。模型决定画质，第一次都需要下载；之后就不会再下载。",
        "en": "All selected. Models determine output quality and are downloaded once."},
    "wizard.models.total": {
        "zh_TW": "合計約 {size} MB", "zh_CN": "合计约 {size} MB", "en": "About {size} MB total"},
    "wizard.model.light": {
        "zh_TW": "通用輕量 — 最快，先試效果用",
        "zh_CN": "通用轻量 — 最快，先试效果用",
        "en": "General lightweight — fastest, good for a trial"},
    "wizard.model.anime": {
        "zh_TW": "動畫輕量 — 線條乾淨",
        "zh_CN": "动画轻量 — 线条干净",
        "en": "Anime lightweight — clean lines"},
    "wizard.model.anime-x4": {
        "zh_TW": "動畫強力 — 線條最銳利",
        "zh_CN": "动画强力 — 线条最锐利",
        "en": "Anime quality — sharpest lines"},
    "wizard.model.x2plus": {
        "zh_TW": "實景 2 倍 — 1080p 升 4K 畫質最佳",
        "zh_CN": "实景 2 倍 — 1080p 升 4K 画质最佳",
        "en": "Photo 2× — best for 1080p to 4K"},
    "wizard.model.x4plus": {
        "zh_TW": "實景 4 倍 — 細節最多，最慢",
        "zh_CN": "实景 4 倍 — 细节最多，最慢",
        "en": "Photo 4× — most detail, slowest"},
    "wizard.model.rife426": {
        "zh_TW": "補幀 — 讓 24fps 變 60fps",
        "zh_CN": "补帧 — 让 24fps 变 60fps",
        "en": "Frame interpolation — 24fps to 60fps"},
    "wizard.download.title": {
        "zh_TW": "正在下載模型", "zh_CN": "正在下载模型", "en": "Downloading models"},
    "wizard.download.done": {
        "zh_TW": "安裝完成，可以開始使用了。",
        "zh_CN": "安装完成，可以开始使用了。",
        "en": "Setup complete. You're ready to go."},
    "wizard.download.failed": {
        "zh_TW": "下載失敗：{name}（稍後重開程式會再試一次）",
        "zh_CN": "下载失败：{name}（稍后重开程序会再试一次）",
        "en": "Download failed: {name} (it will be retried next time)"},
    "wizard.next": {"zh_TW": "下一步", "zh_CN": "下一步", "en": "Next"},
    "wizard.back": {"zh_TW": "上一步", "zh_CN": "上一步", "en": "Back"},
    "wizard.close": {"zh_TW": "結束", "zh_CN": "结束", "en": "Close"},
    "wizard.finish": {"zh_TW": "完成", "zh_CN": "完成", "en": "Finish"},
}

_current = DEFAULT


def detect_language() -> str:
    name = QLocale.system().name()
    if name.startswith("zh_TW") or name.startswith("zh_HK") or name.startswith("zh_MO"):
        return "zh_TW"
    if name.startswith("zh"):
        return "zh_CN"
    return "en"


def set_language(code: str) -> None:
    global _current
    _current = code if code in LANGS else DEFAULT


def language() -> str:
    return _current


def tr(key: str, **kwargs) -> str:
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(_current) or entry.get(DEFAULT) or key
    return text.format(**kwargs) if kwargs else text
