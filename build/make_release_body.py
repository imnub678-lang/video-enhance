"""產生與 NVIDIA 安裝檔相符的 GitHub Release 說明。"""
import hashlib
import json
from pathlib import Path

VERSION = "1.5"
STEM = f"VideoEnhance_NVIDIA_v{VERSION}_setup"

NOTES = """適用於 Windows 10／11 64 位元與 NVIDIA 獨立顯卡。安裝檔包含 PyTorch、FFmpeg 與 ffprobe。第一次使用時，程式會下載並驗證模型。

## 安裝

1. 將 `{stem}.part1` 和 `{stem}.part2` 下載到同一個資料夾。
2. 在該資料夾開啟「命令提示字元」，執行：

   ```bat
   copy /B {stem}.part1+{stem}.part2 {stem}.exe
   ```

3. 雙擊合併後的 `{stem}.exe`。

合併後的安裝檔 SHA256：`{sha256}`

## 這版的變更

- 預設輸出以 `_enhanced` 結尾，防止覆寫原始影片或同名成品。
- 拖入影片時先讀取基本資訊，開始處理後才掃描影格一次。
- 超分保留畫面比例與旋轉方向，補幀依實際時間戳處理可變幀率影片。
- 修正無音軌字幕輸出、提早結束的解碼與分段續傳；硬體編碼器不適用時會回退到軟體編碼。
- 處理日誌新增解碼、推論、影格複製、編碼與分段合併耗時。

已在 Windows／NVIDIA 環境通過 116 項測試與安裝、影片輸出、移除測試。只超分且未啟用補幀時，可變幀率素材仍會按平均幀率輸出。
"""


if __name__ == "__main__":
    build = Path(__file__).resolve().parent
    installer = build.parent / "dist" / "installers" / f"{STEM}.exe"
    with installer.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    body = {
        "tag_name": f"v{VERSION}",
        "name": f"Video Enhance {VERSION} (NVIDIA)",
        "body": NOTES.format(stem=STEM, sha256=digest),
        "draft": True,
        "prerelease": False,
    }
    out = build / "release_body.json"
    out.write_text(json.dumps(body, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out)
