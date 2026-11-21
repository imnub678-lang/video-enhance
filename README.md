# 影片畫質增強工具

本機執行的桌面工具：1080p 影片真超分到 4K，並補幀到 60fps。全程不傳雲端、不限片長。

## 啟動

雙擊 `run.bat`，或：

```bat
cd /d D:\video-enhance
.venv\Scripts\python.exe app\main.py
```

## 用法

1. 把影片拖進視窗（支援 mp4／mov／mkv／avi／m4v／wmv）
2. 選預設
3. 確認主題／副題（預設從檔名以 `_` 分割）
4. 按「開始」

輸出檔名為 `主題_副題.mp4`，預設放在 `D:\AI視頻完成品\`。

## 五個預設

| 預設 | 做什麼 | 適用 |
|---|---|---|
| 平衡 | 超分到 4K + 補幀到 60fps，NVENC 編碼 | 日常默認 |
| 高質量 | 同上，改用 libx265 crf18 | 最終成片，慢約 2 倍 |
| 快速 | 同上，cq21 編碼 | 先看效果 |
| 只補幀 | 不動解析度，只補到 60fps | 已是 4K 的素材 |
| 只超分 | 只超分，不改幀率 | 素材已是 60fps |

實測速度（RTX 5070 Ti Laptop，TensorRT FP16）：7 秒 1080p24 素材跑完整超分＋補幀約 100 秒。10 秒約 2.4 分鐘，60 秒約 14 分鐘。

首次執行會編譯 TensorRT 引擎（SR 約 9 秒、RIFE 4K 約 62 秒），之後引擎快取在 `models/trt_cache/`，載入只要 0.04 秒。不想用 TRT 可設環境變數 `VIDEOTOOL_NO_TRT=1`。

## 支援與不支援

**支援**
- 解析度 4K 以下（含 1440p，一律走 x4 過採樣後降採到 2160p）
- 可變幀率（VFR）素材，會按時間戳重採樣到 60fps
- 手機直拍帶旋轉 metadata 的影片（自動轉正）
- 無音軌影片
- 中文／空格／括號檔名

**不支援（會拒絕或降級）**
- 解析度 >1080p 的超分（可改用「只補幀」）
- HDR 輸入（SDR 10-bit 可以，會轉 8-bit 處理後輸出 10-bit）
- 內封字幕只有 `mov_text` 能保留，ASS／PGS 會丟棄並記日誌
- mp4 不支援的音軌（PCM／DTS／TrueHD）會轉成 AAC 192k

## 模型

放在 `models/`，首次執行自動下載並校驗 SHA256：

| 檔案 | 用途 | 大小 |
|---|---|---|
| `realesr-general-x4v3.pth` | 通用超分 | 4.9 MB |
| `realesr-animevideov3.pth` | 動漫超分 | 2.5 MB |
| `flownet.pkl` | RIFE v4.26 補幀 | 24 MB |

手動下載：刪掉對應檔案再執行一次即可。

## 目錄結構

```
engine/     管線核心（probe、policy、timestamps、sr、fi、pipeline）
app/        GUI 與 worker
presets/    五個預設的參數
tests/      單元與整合測試
```

## 測試

```bat
.venv\Scripts\python.exe -m pytest
```

跳過慢測試：`-m "not slow"`。只跑端到端：`-m integration`。

## 開發備註

- 不使用 `basicsr`，SRVGG 架構自寫（`engine/arch_srvgg.py`），因為 `basicsr` 依賴已被移除的 `torchvision.transforms.functional_tensor`
- 超分有殘差基底（`out += nearest_upsample(x)`），漏掉會輸出全黑
- RIFE 走官方 v4.26 的 `IFNet_HDv3`（`engine/arch_rife.py`），`flownet.pkl` 的 key 帶 `module.` 前綴需剝除
- 推論用 FP16，實測與 FP32 的像素差 0.04（滿分 255）
- 管線全程走 GPU 張量，只在解碼後與編碼前各轉一次 numpy；早期版本每階段都轉，速度差 2.28 倍
- TRT 引擎用固定形狀編譯（SR 800×800 patch、RIFE 2176×3840），所以所有 tile 都補到同尺寸
- `tiled_tensor` 必須顯式傳入 `scale`，否則會對 TRT 引擎做 8×8 探測而觸發 shape guard 錯誤
