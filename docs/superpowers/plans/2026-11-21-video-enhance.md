# 影片畫質增強工具 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建一個本機桌面工具，把 1080p 影片真超分到 4K 並補幀到 60fps，輸出到 `D:\AI視頻完成品\`。

**Architecture:** ffmpeg 解碼子進程吐 `bgr24` 原始幀 → Python 逐幀做 Real-ESRGAN 分塊超分 → RIFE 按時間戳插幀 → 寫進 ffmpeg 編碼子進程（`hevc_nvenc`），音軌直通。PySide6 GUI 用 QProcess 啟動 worker 子進程，透過 stderr 的 JSON 行回報進度。

**Tech Stack:** Python 3.13.14、PyTorch 2.14.1+cu130、PySide6、PyAV、OpenCV、ffmpeg N-127941（`D:\ffmpeg\bin`）、pytest

**Spec:** `D:\video-enhance\docs\superpowers\specs\2026-11-21-video-enhance-design.md`

## Global Constraints

- 專案根目錄：`D:\video-enhance`（路徑不含空格與中文）
- venv：`D:\video-enhance\.venv`，Python 3.13.14
- 不使用 `basicsr`（依賴 `torchvision.transforms.functional_tensor`，新版已移除）
- 超分模型：`realesr-general-x4v3.pth`（x4）與 `realesr-animevideov3.pth`（x4）
- 補幀模型：RIFE `rife47.pth`，走 vendor 的 `IFNet_HDv3`
- 輸出固定 3840×2160、60fps、mp4、`hevc_nvenc -preset p5 -cq 19`、`yuv420p10le`
- 音軌 `-c:a copy`；mp4 不支援的音訊（PCM／DTS／TrueHD）轉 AAC 192k
- 內封字幕僅 `mov_text` 可 copy，其餘放棄並記日誌，不燒錄
- 輸入 >1080p 直接拒絕；HDR／10-bit 輸入拒絕
- 所有推論在子進程，GUI 主執行緒不得阻塞
- 峰值顯存 < 11 GB；tile 由 512 → 384 → 256 自動降級
- 禁止用 bicubic／lanczos 冒充超分

## Review Focus

1. **奇數寬高**（如 1919×1079）——`yuv420p` 要求偶數，使用者會遇到裁切過的片。期望：開跑前自動 pad 到偶數，不報錯。
2. **無音軌影片**——`-c:a copy` 在沒有音軌時會讓 ffmpeg 失敗。期望：自動略過音訊映射，正常出片。
3. **手機直拍帶旋轉 metadata**——不處理會輸出側倒的畫面。期望：解碼時套用 autorotate，輸出正向。
4. **中文／空格／括號檔名**——Windows 路徑常見。期望：解碼、編碼、輸出全鏈路正確處理，不因編碼問題失敗。
5. **0 幀或 1 幀的影片**——無法補幀。期望：明確報錯「素材幀數不足」，不是崩潰或卡死。

---

## File Structure

| 檔案 | 職責 |
|---|---|
| `requirements.txt` | 依賴鎖定 |
| `engine/probe.py` | 呼叫 ffprobe，回傳 `VideoInfo`（解析度、幀率、pix_fmt、旋轉、音軌、字幕、HDR 旗標） |
| `engine/policy.py` | 依 `VideoInfo` 決定 scale、tile、是否補幀、是否拒絕。純函式，無 IO |
| `engine/timestamps.py` | 產生輸出幀排程：`list[FramePlan]`，每個輸出幀對應哪兩個來源幀與插值權重 |
| `engine/ffmpeg_pipe.py` | 解碼／編碼子進程的封裝（啟動、讀幀、寫幀、關閉、錯誤收集） |
| `engine/arch_srvgg.py` | `SRVGGNetCompact` 網路定義與權重載入 |
| `engine/sr.py` | 分塊超分推論 |
| `engine/fi.py` | RIFE 插幀封裝 |
| `engine/models.py` | 模型下載、快取於 `models/`、SHA256 校驗 |
| `engine/progress.py` | 進度 JSON 行協議（寫出與解析） |
| `engine/pipeline.py` | 串接全部，輸出成片 |
| `app/worker.py` | CLI 入口，被 GUI 以子進程啟動 |
| `app/ui/main_window.py` | PySide6 介面 |
| `app/main.py` | GUI 入口 |
| `presets/*.json` | 平衡／高質量／快速／只補幀／只超分 |
| `tests/` | 單元與整合測試 |

---

### Task 1: 專案骨架與測試環境

**Files:**
- Create: `D:\video-enhance\requirements.txt`, `pytest.ini`, `.gitignore`, `tests/__init__.py`

**Interfaces:**
- Produces: 可執行的 `pytest`；`python -c "import torch; torch.cuda.is_available()"` 回 `True`

- [ ] **Step 1: 建立 venv 與依賴**

```bash
cd /d/video-enhance
"C:/Users/imnub/.workbuddy-ai/binaries/python/versions/3.13.12/python.exe" -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu130
.venv/Scripts/python.exe -m pip install PySide6 opencv-python av numpy pytest
```

`requirements.txt` 記錄上述版本（`pip freeze` 後只保留直接依賴，帶版本號）。

- [ ] **Step 2: 驗證 CUDA**

Run: `.venv/Scripts/python.exe -c "import torch;print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"`
Expected: `2.14.1+cu130 True NVIDIA GeForce RTX 5070 Ti Laptop GPU`

- [ ] **Step 3: 建立 pytest 設定**

`pytest.ini` 內容：`[pytest]`、`testpaths = tests`、`addopts = -v`。

`.gitignore`：`.venv/`、`models/`、`__pycache__/`、`*.pyc`、`output/`、`tests/tmp/`。

- [ ] **Step 4: 空測試確認環境**

```python
# tests/test_env.py
import torch

def test_cuda_available():
    assert torch.cuda.is_available()
```

Run: `.venv/Scripts/python.exe -m pytest tests/test_env.py`
Expected: PASS

- [ ] **Step 5: git init 與首次提交**

```bash
git init
git add requirements.txt pytest.ini .gitignore tests/
git commit -m "chore: 專案骨架與 CUDA 環境驗證"
```

---

### Task 2: ffprobe 解析

**Files:**
- Create: `engine/probe.py`, `tests/test_probe.py`, `tests/fixtures/probe_1080p.json`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class VideoInfo:
      width: int; height: int
      fps_num: int; fps_den: int          # 平均幀率，有理數
      frame_count: int                     # 解碼後實際幀數
      pix_fmt: str
      rotation: int                        # 0/90/180/270
      duration: float
      has_audio: bool
      audio_codec: str | None
      subtitle_codecs: tuple[str, ...]
      is_hdr: bool
      is_10bit: bool

  def probe(path: str) -> VideoInfo
  def parse_ffprobe_json(raw: dict) -> VideoInfo
  ```
- 幀率取 `avg_frame_rate`，解析失敗時退回 `r_frame_rate`；`is_hdr` 判定：`color_transfer` 為 `smpte2084` 或 `arib-std-b67`，或 `color_primaries == bt2020`；`is_10bit`：`pix_fmt` 含 `10` 或 `12`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_probe.py
import json, pathlib
from engine.probe import parse_ffprobe_json

FIX = pathlib.Path(__file__).parent / "fixtures"

def test_parse_1080p_sdr_with_audio():
    info = parse_ffprobe_json(json.loads((FIX / "probe_1080p.json").read_text(encoding="utf-8")))
    assert (info.width, info.height) == (1920, 1080)
    assert (info.fps_num, info.fps_den) == (24, 1)
    assert info.pix_fmt == "yuv420p"
    assert info.has_audio is True
    assert info.is_hdr is False
    assert info.is_10bit is False
    assert info.rotation == 0
```

fixture 用真實 `ffprobe -print_format json -show_streams -show_format` 輸出存檔（對 Task 8 產生的測試片跑一次取得）。

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probe.py -v`
Expected: FAIL，`ModuleNotFoundError: engine.probe`

- [ ] **Step 3: 實作 `parse_ffprobe_json` 與 `probe`**

`probe` 執行 `ffprobe -v error -print_format json -show_streams -show_format -count_frames <path>`，`frame_count` 取視訊流的 `nb_read_frames`。`rotation` 從 `side_data_list` 的 `rotation` 取絕對值，缺失為 0。

- [ ] **Step 4: 補三個邊界測試**

```python
def test_no_audio_stream():
    info = parse_ffprobe_json(...)   # 無 audio 流的 fixture
    assert info.has_audio is False and info.audio_codec is None

def test_hdr_detected():
    info = parse_ffprobe_json(...)   # color_transfer=smpte2084
    assert info.is_hdr is True

def test_rotation_90():
    info = parse_ffprobe_json(...)   # side_data rotation=-90
    assert info.rotation == 90
```

- [ ] **Step 5: 跑全部測試**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probe.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add engine/probe.py tests/test_probe.py tests/fixtures/
git commit -m "feat: ffprobe 解析與 VideoInfo"
```

---

### Task 3: 決策層（解析度、倍數、拒絕條件）

**Files:**
- Create: `engine/policy.py`, `tests/test_policy.py`

**Interfaces:**
- Consumes: `VideoInfo`（Task 2）
- Produces:
  ```python
  @dataclass(frozen=True)
  class Plan:
      scale: int            # 2 或 4；0 表示不超分
      tile: int             # 512/384/256；0 表示不分塊
      do_sr: bool
      do_fi: bool
      target_fps: int       # 60
      reject_reason: str | None

  def decide(info: VideoInfo, preset: str) -> Plan
  ```
- 規則（對應 spec §12）：
  - `info.is_hdr or info.is_10bit` → `reject_reason="HDR/10-bit 不支援"`
  - `info.frame_count < 2` → `reject_reason="素材幀數不足"`
  - `width*height > 1920*1080` 且 preset 非「只補幀」→ `reject_reason="解析度已高於 1080p"`
  - `fps >= 60` → `do_fi=False`
  - preset「只補幀」→ `do_sr=False, scale=0`
  - preset「只超分」→ `do_fi=False`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_policy.py
import pytest
from engine.probe import VideoInfo
from engine.policy import decide

def mk(**kw):
    base = dict(width=1920, height=1080, fps_num=24, fps_den=1, frame_count=240,
                pix_fmt="yuv420p", rotation=0, duration=10.0, has_audio=True,
                audio_codec="aac", subtitle_codecs=(), is_hdr=False, is_10bit=False)
    base.update(kw)
    return VideoInfo(**base)

def test_1080p24_balanced_upscales_and_interpolates():
    p = decide(mk(), "balanced")
    assert (p.do_sr, p.scale, p.do_fi, p.target_fps, p.tile) == (True, 4, True, 60, 512)

def test_720p_upscales_with_x4():
    p = decide(mk(width=1280, height=720), "balanced")
    assert (p.do_sr, p.scale) == (True, 4)

def test_over_1080p_rejected():
    p = decide(mk(width=2560, height=1440), "balanced")
    assert p.reject_reason is not None

def test_over_1080p_allowed_for_fi_only():
    p = decide(mk(width=2560, height=1440), "fi_only")
    assert p.reject_reason is None and p.do_sr is False

def test_60fps_skips_interpolation():
    p = decide(mk(fps_num=60), "balanced")
    assert p.do_fi is False

def test_hdr_rejected():
    assert decide(mk(is_hdr=True), "balanced").reject_reason is not None

def test_single_frame_rejected():
    assert decide(mk(frame_count=1), "balanced").reject_reason is not None
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/python.exe -m pytest tests/test_policy.py -v`
Expected: FAIL，`ModuleNotFoundError: engine.policy`

- [ ] **Step 3: 實作 `decide`**

純函式，無 IO。`tile` 依 scale 給：scale==4 → 512；scale==2 → 512；不超分 → 0。preset 名稱：`balanced`／`quality`／`fast`／`fi_only`／`sr_only`，`fast` 用 tile=384。

- [ ] **Step 4: 跑測試**

Run: `.venv/Scripts/python.exe -m pytest tests/test_policy.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add engine/policy.py tests/test_policy.py
git commit -m "feat: 解析度與預設決策層"
```

---

### Task 4: 輸出幀排程（時間戳驅動）

**Files:**
- Create: `engine/timestamps.py`, `tests/test_timestamps.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class FramePlan:
      out_index: int
      src_a: int        # 來源幀索引
      src_b: int
      t: float          # 0.0 = 完全用 src_a；1.0 = 完全用 src_b

  def schedule(n_src: int, src_fps: float, target_fps: int) -> list[FramePlan]
  ```
- 語義：第 `out_index` 個輸出幀的時間 = `out_index / target_fps`；換算到來源時間軸 `t_src = out_index * src_fps / target_fps`；`src_a = floor(t_src)`，`src_b = min(src_a+1, n_src-1)`，`t = t_src - src_a`。`t < 1e-6` 時 `src_b = src_a`（不插值）。
- 總輸出幀數 = `round(n_src * target_fps / src_fps)`，最後一幀索引不超出 `n_src-1`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_timestamps.py
from engine.timestamps import schedule

def test_24_to_60_count_and_bounds():
    plans = schedule(240, 24.0, 60)
    assert len(plans) == 600
    assert all(0 <= p.src_a <= p.src_b < 240 for p in plans)
    assert plans[0].t == 0.0

def test_24_to_60_weights_match_positions():
    plans = schedule(240, 24.0, 60)
    # 輸出第 3 幀時間 0.05s，來源位置 1.2 → src_a=1, t≈0.2
    assert plans[3].src_a == 1
    assert abs(plans[3].t - 0.2) < 1e-6

def test_30_to_60_is_alternating():
    plans = schedule(300, 30.0, 60)
    assert [p.t for p in plans[:4]] == [0.0, 0.5, 0.0, 0.5]

def test_60_to_60_passthrough():
    plans = schedule(60, 60.0, 60)
    assert all(p.src_a == p.src_b for p in plans)

def test_last_frame_never_exceeds():
    plans = schedule(10, 24.0, 60)
    assert max(p.src_b for p in plans) == 9
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/python.exe -m pytest tests/test_timestamps.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 實作 `schedule`**

純算術，無 IO。

- [ ] **Step 4: 跑測試**

Run: `.venv/Scripts/python.exe -m pytest tests/test_timestamps.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add engine/timestamps.py tests/test_timestamps.py
git commit -m "feat: 時間戳驅動的輸出幀排程"
```

---

### Task 5: 網路定義與權重載入

**Files:**
- Create: `engine/arch_srvgg.py`, `engine/models.py`, `tests/test_arch.py`
- Vendor: `vendor/Practical-RIFE/`（`git clone --depth 1 https://github.com/hzwer/Practical-RIFE`）

**Interfaces:**
- Produces:
  ```python
  # engine/arch_srvgg.py
  class SRVGGNetCompact(nn.Module):
      def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4)
      def forward(self, x: torch.Tensor) -> torch.Tensor

  def load_srvgg(weights_path: str, upscale: int) -> SRVGGNetCompact   # eval() + cuda()

  # engine/models.py
  MODELS: dict[str, tuple[str, str]]   # 名稱 -> (URL, SHA256)
  def ensure_model(name: str, dest_dir: str) -> str
  ```
- `MODELS` 條目：`realesr-general-x4v3`、`realesr-animevideov3`、`rife47`
- `SRVGGNetCompact` 結構：`conv_first(3→num_feat, 3)` → `num_conv` 個 `conv(3x3)+PReLU` → `conv_last(num_feat→3*upscale², 3)` → `PixelShuffle(upscale)`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_arch.py
import torch
from engine.arch_srvgg import SRVGGNetCompact

def test_srvgg_output_shape_x4():
    m = SRVGGNetCompact(upscale=4).eval()
    with torch.no_grad():
        out = m(torch.zeros(1, 3, 64, 64))
    assert out.shape == (1, 3, 256, 256)

def test_srvgg_roundtrip_deterministic():
    m = SRVGGNetCompact(upscale=4).eval()
    x = torch.rand(1, 3, 32, 32)
    with torch.no_grad():
        assert torch.allclose(m(x), m(x))
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/python.exe -m pytest tests/test_arch.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 實作 `SRVGGNetCompact`**

- [ ] **Step 4: 跑測試**

Run: `.venv/Scripts/python.exe -m pytest tests/test_arch.py -v`
Expected: 2 passed

- [ ] **Step 5: Vendor RIFE 並驗證權重可載入**

```bash
git clone --depth 1 https://github.com/hzwer/Practical-RIFE vendor/Practical-RIFE
```

測試：從 `vendor/Practical-RIFE` import `IFNet_HDv3.IFNet`，載入 `rife47.pth`，`forward` 兩張 64×64 幀回傳單張 64×64。權重缺失時 `pytest.skip`。

- [ ] **Step 6: 實作 `ensure_model`（下載 + SHA256 校驗 + 快取）**

`models/` 目錄不存在則建立。已存在且 SHA256 相符則直接回傳路徑。不符則重下。下載用 `urllib.request`，帶進度回呼。

- [ ] **Step 7: 下載三個模型並記錄實際 SHA256**

Run: `.venv/Scripts/python.exe -c "from engine.models import ensure_model; [print(ensure_model(n,'models')) for n in ('realesr-general-x4v3','realesr-animevideov3','rife47')]"`
Expected: 印出三個檔案路徑，`models/` 下檔案總大小 < 40 MB

- [ ] **Step 8: Commit**

```bash
git add engine/arch_srvgg.py engine/models.py tests/test_arch.py .gitmodules vendor 2>/dev/null
git commit -m "feat: SRVGG 架構、RIFE vendor 與模型管理"
```

---

### Task 6: 分塊超分推論

**Files:**
- Create: `engine/sr.py`, `tests/test_sr.py`

**Interfaces:**
- Consumes: `load_srvgg`（Task 5）
- Produces:
  ```python
  class SuperResolver:
      def __init__(self, weights: str, upscale: int, tile: int, tile_pad: int = 16, device: str = "cuda")
      def __call__(self, frame_bgr: np.ndarray) -> np.ndarray   # HxWx3 uint8 -> (H*s)x(W*s)x3 uint8
      def resize_to(self, frame_bgr: np.ndarray, out_h: int, out_w: int) -> np.ndarray  # INTER_AREA 降採
  ```
- 分塊邏輯：按 `tile` 切格，每格向外擴 `tile_pad`，推論後裁掉 padding 再貼回。邊緣格不超出影像範圍。
- 顯存不足（`torch.cuda.OutOfMemoryError`）時 `tile //= 2`，最小 128，重試一次

- [ ] **Step 1: 寫失敗測試（用恆等模型驗證分塊拼接正確）**

```python
# tests/test_sr.py
import numpy as np, torch
from engine.sr import tiled_infer

class Identity(torch.nn.Module):
    def forward(self, x):
        return x

def test_tiled_matches_whole():
    img = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
    whole = tiled_infer(Identity(), img, tile=0, pad=16, device="cpu")
    tiled = tiled_infer(Identity(), img, tile=64, pad=16, device="cpu")
    assert np.array_equal(whole, tiled)

def test_tiled_odd_sizes():
    img = np.random.randint(0, 255, (97, 131, 3), dtype=np.uint8)
    out = tiled_infer(Identity(), img, tile=32, pad=8, device="cpu")
    assert out.shape == img.shape
```

`tiled_infer(model, img_bgr, tile, pad, device)` 是模組級函式，`SuperResolver.__call__` 內部呼叫它。

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sr.py -v`
Expected: FAIL，`ImportError: cannot import name 'tiled_infer'`

- [ ] **Step 3: 實作 `tiled_infer`**

張量轉換：`img[:, :, ::-1] / 255.0` → CHW → unsqueeze → `.to(device)`；輸出 `clamp(0,1)` → `*255` → uint8 → BGR。`tile=0` 表示整張一次推論。

- [ ] **Step 4: 跑測試**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sr.py -v`
Expected: 2 passed

- [ ] **Step 5: 實作 `SuperResolver` 與 OOM 降級**

- [ ] **Step 6: 真模型冒煙測試（標記 slow）**

```python
@pytest.mark.slow
def test_real_model_upscales_1080p_tile():
    sr = SuperResolver("models/realesr-general-x4v3.pth", 4, tile=512)
    out = sr(np.zeros((1080, 1920, 3), dtype=np.uint8))
    assert out.shape == (4320, 7680, 3)
```

Run: `.venv/Scripts/python.exe -m pytest tests/test_sr.py -m slow -v`
Expected: PASS，峰值顯存 < 11 GB（測試內 `torch.cuda.max_memory_allocated()` 斷言）

- [ ] **Step 7: Commit**

```bash
git add engine/sr.py tests/test_sr.py
git commit -m "feat: 分塊超分推論與顯存降級"
```

---

### Task 7: RIFE 插幀

**Files:**
- Create: `engine/fi.py`, `tests/test_fi.py`

**Interfaces:**
- Consumes: `vendor/Practical-RIFE` 的 `IFNet`
- Produces:
  ```python
  class Interpolator:
      def __init__(self, weights: str, device: str = "cuda")
      def blend(self, a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray
  ```
- `t == 0` 回傳 `a`（不進模型）；`t == 1` 回傳 `b`；`0 < t < 1` 走模型
- 張量：BGR uint8 → RGB float [0,1] → CHW → unsqueeze；`IFNet` 簽名為 `forward(img0, img1, timestep, scale=1.0)`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_fi.py
import numpy as np, pytest
from engine.fi import Interpolator

def test_t_zero_returns_a():
    it = Interpolator.__new__(Interpolator)   # 不載模型
    a = np.full((8, 8, 3), 10, np.uint8)
    b = np.full((8, 8, 3), 200, np.uint8)
    assert np.array_equal(it.blend(a, b, 0.0), a)

def test_t_one_returns_b():
    it = Interpolator.__new__(Interpolator)
    a = np.full((8, 8, 3), 10, np.uint8)
    b = np.full((8, 8, 3), 200, np.uint8)
    assert np.array_equal(it.blend(a, b, 1.0), b)

@pytest.mark.slow
def test_midpoint_shape_and_range():
    it = Interpolator("models/rife47.pth")
    a = np.zeros((64, 64, 3), np.uint8)
    b = np.full((64, 64, 3), 255, np.uint8)
    out = it.blend(a, b, 0.5)
    assert out.shape == (64, 64, 3) and out.dtype == np.uint8
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fi.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 實作 `Interpolator`**

`__init__` 載權重、`eval()`、`cuda()`、`torch.no_grad()` 常駐。模型輸入需 32 的倍數，非整數倍時先 pad 到倍數再裁回。

- [ ] **Step 4: 跑測試**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fi.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add engine/fi.py tests/test_fi.py
git commit -m "feat: RIFE 插幀封裝"
```

---

### Task 8: ffmpeg 管線封裝

**Files:**
- Create: `engine/ffmpeg_pipe.py`, `tests/test_ffmpeg_pipe.py`, `tests/conftest.py`

**Interfaces:**
- Produces:
  ```python
  class Decoder:
      def __init__(self, path: str, width: int, height: int)   # 套 autorotate、pad 到偶數
      def read(self) -> np.ndarray | None                       # BGR，結束回 None
      def close(self) -> None
      def __len__(self) -> int                                  # 幀數

  class Encoder:
      def __init__(self, path: str, width: int, height: int, fps: int,
                   source: str, audio_codec: str | None, subtitle_codec: str | None,
                   crf: int = 19, codec: str = "hevc_nvenc")
      def write(self, frame_bgr: np.ndarray) -> None
      def close(self) -> None                                   # 等待完成並檢查 returncode
  ```
- `conftest.py` 提供 `make_clip` fixture：簽名 `make_clip(fps=24, seconds=1, width=320, height=240, has_audio=True, rotation=0)`，用 ffmpeg 生成測試片（`testsrc2`）。`rotation` 非 0 時寫入 `-metadata:s:v rotate=90`。回傳絕對路徑字串。

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_ffmpeg_pipe.py
import numpy as np
from engine.ffmpeg_pipe import Decoder, Encoder

def test_decoder_frame_count(make_clip):
    d = Decoder(make_clip(fps=24, seconds=1), 320, 240)
    frames = []
    while (f := d.read()) is not None:
        frames.append(f)
    d.close()
    assert len(frames) == 24 and frames[0].shape == (240, 320, 3)

def test_decoder_handles_odd_dimensions(make_clip):
    path = make_clip(width=319, height=241)
    d = Decoder(path, 320, 242)
    assert d.read() is not None
    d.close()

def test_encoder_without_audio(make_clip, tmp_path):
    src = make_clip(has_audio=False)
    out = str(tmp_path / "out.mp4")
    d, e = Decoder(src, 320, 240), Encoder(out, 320, 240, 24, src, None, None)
    while (f := d.read()) is not None:
        e.write(f)
    d.close(); e.close()
    assert Decoder(out, 320, 240).read() is not None

def test_encoder_unicode_path(make_clip, tmp_path):
    src = make_clip()
    out = str(tmp_path / "測試 檔（1）.mp4")
    ... 同上迴圈 ...
    assert Decoder(out, 320, 240).read() is not None

def test_decoder_applies_rotation(make_clip):
    path = make_clip(width=320, height=240, rotation=90)
    d = Decoder(path, 240, 320)          # 旋轉後寬高互換
    f = d.read()
    d.close()
    assert f.shape == (320, 240, 3)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ffmpeg_pipe.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 實作 `Decoder`**

ffmpeg 參數：`-v error -i <path> -vf "scale=w:h:flags=bicubic" -f rawvideo -pix_fmt bgr24 -`。`autorotate` 為 ffmpeg 預設行為，無需額外參數。`subprocess.Popen(..., stdout=PIPE, stderr=PIPE, creationflags=CREATE_NO_WINDOW)`。寬高由呼叫方傳入（已 pad 到偶數），`-vf scale` 保證輸出尺寸一致。

- [ ] **Step 4: 實作 `Encoder`**

參數：`-f rawvideo -pix_fmt bgr24 -s WxH -r 60 -i - -i <source> -map 0:v -map 1:a? -c:v hevc_nvenc -preset p5 -cq 19 -pix_fmt yuv420p10le -c:a copy -movflags +faststart -y <out>`。音訊不可 copy 時改 `-c:a aac -b:a 192k`。字幕 `-map 1:s? -c:s copy` 僅當 `subtitle_codec == "mov_text"`。

- [ ] **Step 5: 跑測試**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ffmpeg_pipe.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add engine/ffmpeg_pipe.py tests/test_ffmpeg_pipe.py tests/conftest.py
git commit -m "feat: ffmpeg 解碼與編碼管線封裝"
```

---

### Task 9: 進度協議與 worker 入口

**Files:**
- Create: `engine/progress.py`, `app/worker.py`, `tests/test_progress.py`, `tests/test_worker.py`

**Interfaces:**
- Produces:
  ```python
  # engine/progress.py
  def emit(stage: str, done: int, total: int) -> None      # 寫 stderr，一行 JSON
  def parse(line: str) -> dict | None                       # 非 JSON 或無 stage 回 None

  # app/worker.py
  def build_parser() -> argparse.ArgumentParser
  # 參數：--input --output --preset --title --subtitle --models-dir --log
  def main(argv: list[str] | None = None) -> int            # 0 成功、2 參數錯、3 決策拒絕、1 執行錯
  ```
- 進度行格式：`{"stage":"sr","done":120,"total":600}`；`stage` ∈ `probe`/`sr`/`fi`/`encode`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_progress.py
from engine.progress import parse

def test_parse_valid():
    assert parse('{"stage":"sr","done":1,"total":2}') == {"stage": "sr", "done": 1, "total": 2}

def test_parse_garbage():
    assert parse("ffmpeg: some error") is None

def test_parse_missing_stage():
    assert parse('{"done":1}') is None
```

```python
# tests/test_worker.py
from app.worker import main

def test_rejects_over_1080p(make_clip, tmp_path):
    src = make_clip(width=2560, height=1440)
    rc = main(["--input", src, "--output", str(tmp_path / "o.mp4"), "--preset", "balanced"])
    assert rc == 3

def test_missing_input_returns_2(tmp_path):
    assert main(["--input", str(tmp_path / "nope.mp4"), "--preset", "balanced"]) == 2
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/python.exe -m pytest tests/test_progress.py tests/test_worker.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 實作 `progress.py` 與 `worker.py` 骨架**

`worker.main` 流程：`probe` → `decide` → 拒絕則印原因回 3 → 建輸出目錄 → 呼叫 `pipeline.run(...)` → 回 0。`pipeline` 先寫成拋 `NotImplementedError` 的樁。

- [ ] **Step 4: 跑測試**

Run: `.venv/Scripts/python.exe -m pytest tests/test_progress.py tests/test_worker.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add engine/progress.py app/worker.py tests/test_progress.py tests/test_worker.py
git commit -m "feat: 進度協議與 worker 入口"
```

---

### Task 10: 管線串接（端到端）

**Files:**
- Create: `engine/pipeline.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `probe`、`decide`、`schedule`、`SuperResolver`、`Interpolator`、`Decoder`、`Encoder`、`emit`
- Produces:
  ```python
  def run(input_path: str, output_path: str, preset: str,
          models_dir: str = "models", on_progress=None) -> None
  ```
- 流程：解碼 → 逐幀超分（若 `do_sr`）→ 依 `schedule` 插幀 → 寫入編碼器。超分結果存 ring buffer（只保留 `schedule` 需要的前後兩幀）
- 進度：每 10 幀 `emit`

- [ ] **Step 1: 寫失敗整合測試（小尺寸，跳過真模型）**

```python
# tests/test_pipeline.py
import pytest
from engine.pipeline import run
from engine.probe import probe

@pytest.mark.integration
def test_end_to_end_fi_only_60fps(make_clip, tmp_path):
    src = make_clip(fps=24, seconds=1, width=320, height=240)
    out = str(tmp_path / "out.mp4")
    run(src, out, preset="fi_only", on_progress=lambda **k: None)
    info = probe(out)
    assert (info.width, info.height) == (320, 240)
    assert info.fps_num / info.fps_den == pytest.approx(60, abs=0.5)
    assert info.duration == pytest.approx(1.0, abs=0.15)

@pytest.mark.integration
@pytest.mark.slow
def test_end_to_end_sr_and_fi(make_clip, tmp_path):
    src = make_clip(fps=24, seconds=1, width=320, height=240)
    out = str(tmp_path / "out4k.mp4")
    run(src, out, preset="fast")
    info = probe(out)
    assert (info.width, info.height) == (3840, 2160)
    assert info.duration == pytest.approx(1.0, abs=0.2)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: FAIL，`NotImplementedError`

- [ ] **Step 3: 實作 `run`**

- [ ] **Step 4: 跑 fi_only 整合測試**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pipeline.py::test_end_to_end_fi_only_60fps -v`
Expected: PASS

- [ ] **Step 5: 跑完整超分整合測試**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -m slow -v`
Expected: PASS，輸出 3840×2160

- [ ] **Step 6: 人工驗證一幀的細節**

抽輸出第 30 幀存 PNG，同時用 bicubic 把原片放大到 4K 存 PNG，並排看。超分版本邊緣應更銳、無光暈。

- [ ] **Step 7: Commit**

```bash
git add engine/pipeline.py tests/test_pipeline.py
git commit -m "feat: 端到端管線"
```

---

### Task 11: 預設檔

**Files:**
- Create: `presets/balanced.json`, `quality.json`, `fast.json`, `fi_only.json`, `sr_only.json`, `engine/presets.py`, `tests/test_presets.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class Preset:
      name: str; label: str; do_sr: bool; do_fi: bool
      model: str            # realesr-general-x4v3 / realesr-animevideov3
      tile: int; encoder: str; crf: int
  def load(name: str, presets_dir: str = "presets") -> Preset
  def all_presets(presets_dir: str = "presets") -> list[Preset]
  ```
- 五個預設的具體值依 spec §9 與 §12：`quality` 用 `libx265 crf18`；`balanced`／`fast`／`sr_only` 用 `hevc_nvenc`；`fast` 的 tile 為 384；`fi_only` 的 `do_sr=False`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_presets.py
from engine.presets import load, all_presets

def test_balanced_values():
    p = load("balanced")
    assert (p.do_sr, p.do_fi, p.tile, p.encoder, p.crf) == (True, True, 512, "hevc_nvenc", 19)

def test_fast_uses_smaller_tile():
    assert load("fast").tile == 384

def test_fi_only_disables_sr():
    assert load("fi_only").do_sr is False

def test_all_five_present():
    assert {p.name for p in all_presets()} == {"balanced","quality","fast","fi_only","sr_only"}
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/python.exe -m pytest tests/test_presets.py -v`
Expected: FAIL

- [ ] **Step 3: 寫五個 JSON 與 `engine/presets.py`**

- [ ] **Step 4: 跑測試**

Run: `.venv/Scripts/python.exe -m pytest tests/test_presets.py -v`
Expected: 4 passed

- [ ] **Step 5: 讓 `worker` 讀預設而非硬編碼**

`worker.main` 改為先 `load(args.preset)` 驗證預設存在（不存在回 2），再把**預設名稱字串**傳給 `decide` 與 `run`——兩者內部各自 `load`，簽名不變。重跑 Task 9、10、3 的測試確認未破壞。

Run: `.venv/Scripts/python.exe -m pytest tests/test_worker.py tests/test_pipeline.py tests/test_policy.py -v`
Expected: 全 PASS

- [ ] **Step 6: Commit**

```bash
git add presets/ engine/presets.py tests/test_presets.py app/worker.py
git commit -m "feat: 五個預設與 worker 接入"
```

---

### Task 12: 桌面 GUI

**Files:**
- Create: `app/ui/main_window.py`, `app/main.py`, `tests/test_gui_smoke.py`

**Interfaces:**
- Consumes: `Preset`／`all_presets`、worker CLI 契約（Task 9）
- Produces: `MainWindow(QMainWindow)`，可 `python app/main.py` 啟動

**介面元素（自上而下）：**
1. 拖放區：`QLabel`，接受 `.mp4/.mov/.mkv/.avi`，顯示檔名、解析度、幀率、時長
2. 預設下拉：五個 `Preset.label`
3. 兩個 `QLineEdit`：主題、副題（選檔後自動從原檔名推導）
4. 輸出路徑：`QLineEdit` + 瀏覽按鈕，預設 `D:\AI視頻完成品`
5. `QProgressBar` + 狀態文字（`階段 / 已處理幀數`）
6. 按鈕：開始、中止（執行中才啟用）
7. `QPlainTextEdit`（唯讀）：日誌

**行為：**
- 開始：`QProcess` 啟動 `.venv/Scripts/python.exe app/worker.py --input ... --output ... --preset ...`
- 讀 `readyReadStandardError`，逐行 `progress.parse`，更新進度條；非 JSON 行寫進日誌
- 中止：`terminate()`，3 秒後 `kill()`，刪除半成品檔
- 完成：狀態列顯示耗時與輸出路徑

- [ ] **Step 1: 寫 GUI 冒煙測試（offscreen）**

```python
# tests/test_gui_smoke.py
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow

def test_window_builds_with_five_presets():
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    assert w.preset_combo.count() == 5
    assert w.btn_start.isEnabled() and not w.btn_stop.isEnabled()

def test_name_derived_from_filename():
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w.set_input_path(r"C:\x\相對論_時空扭曲結構.mp4")
    assert w.edit_title.text() == "相對論"
    assert w.edit_subtitle.text() == "時空扭曲結構"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/python.exe -m pytest tests/test_gui_smoke.py -v`
Expected: FAIL，`ModuleNotFoundError: app.ui.main_window`

- [ ] **Step 3: 實作 `MainWindow`**

檔名推導規則：去副檔名，以第一個 `_` 分割為主題／副題；無 `_` 時整串當主題，副題留空。

- [ ] **Step 4: 跑測試**

Run: `.venv/Scripts/python.exe -m pytest tests/test_gui_smoke.py -v`
Expected: 2 passed

- [ ] **Step 5: 人工驗證**

Run: `.venv/Scripts/python.exe app/main.py`
拖入一段真實 1080p 片，選「快速」，開始，確認進度條推進、日誌有內容、中止按鈕有效、GUI 不卡。

- [ ] **Step 6: Commit**

```bash
git add app/ui/main_window.py app/main.py tests/test_gui_smoke.py
git commit -m "feat: PySide6 桌面介面"
```

---

### Task 13: 實測校準與打包啟動

**Files:**
- Create: `run.bat`, `README.md`
- Modify: `docs/superpowers/specs/2026-11-21-video-enhance-design.md`（§9 耗時表）

- [ ] **Step 1: 跑三段真實素材實測**

用 10 秒 1080p 24fps 的 AI 生成片，分別跑 `fast`／`balanced`／`quality`，記錄：實際耗時、峰值顯存、輸出檔案大小。

- [ ] **Step 2: 把實測值寫回 spec §9**

替換估算值為實測值，標註測試日期與素材。

- [ ] **Step 3: 寫 `run.bat`**

```bat
@echo off
cd /d D:\video-enhance
start "" ".venv\Scripts\pythonw.exe" app\main.py
```

- [ ] **Step 4: 寫 `README.md`**

內容：怎麼啟動、五個預設的差別、支援與不支援的輸入（對應 spec §12）、模型放在哪、怎麼換模型。

- [ ] **Step 5: 全測試跑一遍**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 全 PASS（`slow` 與 `integration` 標記的項目視時間選擇性執行）

- [ ] **Step 6: Commit**

```bash
git add run.bat README.md docs/
git commit -m "docs: 實測校準與啟動腳本"
```
