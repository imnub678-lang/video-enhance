# 影片畫質增強工具

本機執行的桌面工具：影片超分到 4K、補幀到 60 或 120fps，兩者可獨立開關。全程不傳雲端、不限片長、中斷可續傳。

## 系統需求

- Windows 10／11 64-bit
- **NVIDIA 獨立顯卡**（CUDA 版）；AMD 與純 CPU 環境請見下方說明
- 建議 8 GB 以上顯存。顯存較小時程式會自動縮小處理分塊（≥8GB 用 512、≥6GB 用 384、其餘 256），降低 OOM 風險

> 目前提供的安裝檔是 **NVIDIA 版**。AMD 需要 Windows 版 ROCm 執行環境，官方 PyTorch 尚未提供對應 wheel；純 CPU 環境在首啟掃描時會被擋下，不提供入口。

## 安裝

### 一般使用者：安裝程式

到 [Releases](../../releases) 下載 `VideoEnhance_NVIDIA_v1.0.0_setup`。安裝檔 3.8 GB，超過 GitHub 單檔案 2 GB 上限，拆成 `.part1` 與 `.part2` 兩卷。兩個檔案都下載到**同一個資料夾**後，在該資料夾執行：

```bat
copy /B VideoEnhance_NVIDIA_v1.0.0_setup.part1+VideoEnhance_NVIDIA_v1.0.0_setup.part2 VideoEnhance_NVIDIA_v1.0.0_setup.exe
```

再雙擊合併出的 exe 安裝。安裝不需要系統管理員權限，torch、ffmpeg 與所有依賴都已打包，不需另外安裝 Python 或環境。

### 從原始碼執行

需要先自行安裝 [ffmpeg](https://www.gyan.dev/ffmpeg/builds/) 並加入 PATH（原始碼模式沒有打包 ffmpeg），接著：

```bat
git clone https://github.com/imnub678-lang/video-enhance.git
cd video-enhance
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app\main.py
```

或直接雙擊 `run.bat`（需先建立 `.venv`）。

## 第一次啟動

1. **選輸出資料夾**：只問一次，之後記在 QSettings
2. **掃描裝置**：顯示顯卡、顯存、CPU 核心、記憶體、可用磁碟、ffmpeg 路徑
3. **確認模型清單**：六個模型預設全勾（合計約 178 MB），可取消不需要的
4. **下載模型**：逐項下載並做 SHA256 校驗

模型放在 `%LOCALAPPDATA%\VideoEnhance\models\`（原始碼模式放在專案 `models\`）。解除安裝不會刪除已下載的模型。

介面會依系統語言自動切換繁體中文／簡體中文／英文。

## 用法

1. 把影片拖進視窗（或按「選擇影片」，支援 mp4／mov／mkv／avi／m4v／wmv）
2. 選**素材類型**：實拍／動畫
3. 選**畫質**：實拍有快／標準／最佳；動畫只有快／最佳
4. 勾選要做的事：☑ 超分到 4K、☑ 補幀
5. 選補幀目標幀率、編碼檔位
6. 確認主題／副題（預設從檔名以 `_` 分割）與輸出目錄
7. 按「開始」

「素材 × 畫質」會自動對應到適合的模型，不需要選技術模型名稱：

| 素材 | 畫質 | 模型 | 倍率 |
|---|---|---|---|
| 實拍 | 快 | `realesr-general-x4v3` | 4× |
| 實拍 | 標準 | `x2plus`（來源 ≥1000p）或 `light` | 2× / 4× |
| 實拍 | 最佳 | `RealESRGAN_x4plus` | 4× |
| 動畫 | 快 | `realesr-animevideov3` | 4× |
| 動畫 | 最佳 | `RealESRGAN_x4plus_anime_6B` | 4× |

倍率是「模型倍率」，輸出目標一律 4K。`x2` 適合來源需要約 2 倍的情況（1080p→4K 剛好 2.00×，沒有多餘重採樣）；來源低於 540p 時 `x2` 不足，剩下靠插值會偏糊。

**重要**：`x2plus`／`x4plus` 是照片模型，用在動漫／插畫上會把線條抹平（實測銳度掉到通用模型的 50–70%）。動漫內容請選動畫；反之動畫模型用在實景素材上會有塑料感。

取消勾選某項時，對應的下拉選單會變灰。下方提示列會依素材解析度算出「需要幾倍」並給建議。

## 補幀目標

RIFE v4.26 依時間戳插幀，非整數倍也能正確處理（24→60、24→120、30→120）。

- 60fps 來源 + 目標 60 → 略過補幀（日誌會說明）
- 60fps 來源 + 目標 120 → 每兩幀插一幀，時長不變，檔案約翻倍
- 24fps 來源 + 目標 120 → 每幀插四幀

**預設用 60。** 實測同一支 1440p60 素材：4K60 184 秒 / 28 MB，4K120 344 秒 / 47 MB（1.9 倍時間、1.7 倍檔案）。120 只在需要慢動作或高動態特寫的片段才划算，整片跑不建議。

## 編碼檔位

| 檔位 | 編碼器 | 參數 | 相對耗時 | 檔案 |
|---|---|---|---|---|
| 標準（預設） | `hevc_nvenc` | cq19 | 1.0× | 基準 |
| 快速 | `hevc_nvenc` | cq21 | 約 1.0× | 小 1.2% |
| 小檔案 | `libx265` | crf18 | **4.2×** | **小 45%** |

「小檔案」只改編碼，**超分結果與標準完全相同**。要更好的畫面請調畫質，不要靠這個檔位。

標準與快速在 NVENC 上幾乎沒有差別：實測同一支 1080p24 3 秒 → 4K60，耗時 60 秒 vs 61 秒，檔案 11.94 MB vs 11.80 MB，SSIM Y 0.9988。瓶頸在超分不在編碼，所以預設選畫質優先的標準，沒有實質成本。

AMD 顯卡會自動改用 `hevc_amf`；沒有可用的硬體編碼器時退回 `libx265`。

## 斷點續傳

輸出會切成每 10 秒一段分別編碼，暫存在輸出目錄的 `.<檔名>.parts\`。每完成一段就更新 `manifest.json`。

- 中斷後重跑同一支素材，**已完成的段落直接跳過**，只補剩下的
- manifest 記錄輸入檔的大小與修改時間、超分／補幀開關、模型、編碼參數；任一項不同就整個作廢重來，不會混用舊片段
- 全部完成後用 ffmpeg 串接，並從原始素材掛回音軌與內嵌字幕，最後清除暫存目錄

要強制重跑，刪掉 `.<檔名>.parts\` 或用 `--no-resume`。

## 速度

RTX 5070 Ti Laptop，TensorRT FP16。實測 9.62 秒 1440p60 素材：

| 輸出 | 耗時 | 檔案 |
|---|---|---|
| 4K60 | 184 秒 | 28 MB |
| 4K120 | 344 秒 | 47 MB |

耗時幾乎全部是 GPU 計算：4K60 中超分佔 161 秒；4K120 再加上補幀 136 秒（575 幀 × 237ms）。

首次執行會編譯 TensorRT 引擎（SR 約 6 秒、RRDBNet 45–55 秒），之後快取在模型目錄的 `trt_cache\`。不想用 TRT 可設環境變數 `VIDEOTOOL_NO_TRT=1`。**補幀不使用 TRT**，原因見開發備註。

其他 1080p24 3 秒 → 4K60 端到端實測：`anime` 44 秒、`light` 46 秒、`x2plus` 76 秒、`anime-x4` 約 70 秒（首次含 TRT 編譯 113 秒）、`x4plus` 約 550 秒（推算）。

解碼與編碼各跑獨立執行緒，但實測在 1080p→4K 這種 GPU 滿載的情境只快 4%；小素材（I/O 佔比高）可快 40%。

## 支援與不支援

**支援**
- 解析度 4K 以下（1440p 也能超分，按模型倍率放大後重採樣到 2160p）
- 可變幀率（VFR）素材，按時間戳重採樣
- 手機直拍帶旋轉 metadata 的影片（自動轉正）
- 無音軌影片
- 中文／空格／括號檔名

**不支援（會拒絕或降級）**
- 解析度已達 4K 的素材做超分（可取消勾選超分）
- HDR 輸入（SDR 10-bit 可以，會轉 8-bit 處理後輸出 10-bit）
- 內嵌字幕只有 `mov_text` 能保留，ASS／PGS 會丟棄
- mp4 不支援的音軌（PCM／DTS／TrueHD）會轉成 AAC 192k

## 模型

首啟精靈會自動下載並校驗 SHA256：

| 檔案 | 用途 | 大小 |
|---|---|---|
| `realesr-general-x4v3.pth` | 通用超分（輕量） | 4.9 MB |
| `realesr-animevideov3.pth` | 動漫超分（輕量） | 2.5 MB |
| `RealESRGAN_x2plus.pth` | 實景 2 倍超分 | 64 MB |
| `RealESRGAN_x4plus.pth` | 實景 4 倍超分 | 64 MB |
| `RealESRGAN_x4plus_anime_6B.pth` | 動漫 4 倍超分（強力） | 18 MB |
| `flownet.pkl` | RIFE v4.26 補幀 | 24 MB |

要重新下載，刪掉對應檔案再重跑精靈即可。

## 目錄結構

```
app/         GUI、worker、設定與 i18n
  ui/        主視窗、玻璃外殼、主題、首啟精靈
engine/      管線核心（probe、policy、timestamps、sr、fi、pipeline、backend）
encoders/    編碼檔位（standard／fast／small）
build/       PyInstaller spec、Inno Setup 腳本、圖示產生器
tests/       單元與整合測試
```

## 打包

```bat
.venv\Scripts\python.exe -m PyInstaller build/video_enhance.spec --noconfirm --clean
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\setup_nvidia.iss
```

AMD 版需先在 ROCm 版 torch 環境下產出 `dist\VideoEnhance-AMD`，再執行 `build\setup_amd.iss`。

## 測試

```bat
.venv\Scripts\python.exe -m pytest
```

跳過慢測試：`-m "not slow"`。跳過端到端：`-m "not integration"`。只跑端到端：`-m integration`。

## 開發備註

- 不使用 `basicsr`，SRVGG 與 RRDBNet 架構都自寫（`engine/arch_srvgg.py`、`engine/arch_rrdb.py`），因為 `basicsr` 依賴已被移除的 `torchvision.transforms.functional_tensor`
- 超分有殘差基底（`out += nearest_upsample(x)`），漏掉會輸出全黑
- `RealESRGAN_x2plus` 的 `conv_first` 是 12 通道（內部 `pixel_unshuffle(x, 2)` 把 3 通道展開），x4 版是 3 通道；`load_rrdb` 靠這個差異自動判斷倍率
- `SuperResolver` 依權重檔名前綴選架構：`RealESRGAN_*` 走 RRDBNet，其餘走 SRVGG
- RIFE 走官方 v4.26 的 `IFNet_HDv3`（`engine/arch_rife.py`），`flownet.pkl` 的 key 帶 `module.` 前綴需剝除
- **補幀不用 TensorRT**：編譯出來的 IFNet 引擎不尊重時間參數，同一組輸入餵 t=0.25/0.5/0.75 得到幾乎相同輸出（4K 下位置比例恆為 1.00，等於回傳後一張原幀），補幀變成複製幀。eager 在 4K 單次 0.18 秒、位置比例 0.28/0.53/0.83 正確，因此 `Interpolator(use_trt=False)` 為預設
- 推論用 FP16，實測與 FP32 的像素差 0.04（滿分 255）
- 管線全程走 GPU 張量，只在解碼後與編碼前各轉一次 numpy；早期版本每階段都轉，速度差 2.28 倍
- **`tensor_to_frame` 必須用非就地的 `clamp`**：補幀時 `t=0` 的輸出幀就是 `pending` 裡的來源張量本身，`clamp_` 會把它從 0–1 汙染成 0–255，下一個插幀就把污染值餵進 RIFE。舊版因此讓每支補幀成品的**最後一幀變成純白**
- **來源幀率不能用 `frame_count/duration` 推算**：容器時長常含音軌尾巴（實測 576 幀 / 9.6212 秒 = 59.868，實際 60.0）。這個誤差會讓原本落在整數位置的輸出幀得到 `t=0.998x`，每個原幀都白跑一次補幀網路（實測補幀次數 575 → 1150，全片慢 22%）。`_src_fps` 改用「時長與幀數是否相符」判斷 CFR，VFR 才回退到推算值
- `schedule` 會把 `t` 在 1e-6 內吸附到精確的 0 或 1：`t=1` 等於下一對的 `t=0`，不吸附就會對原幀做無意義的插值
- TRT 引擎用固定形狀編譯（SR 800×800 或 416×416 patch、RIFE 2176×3840），所以所有 tile 都補到同尺寸
- `tiled_tensor` 必須顯式傳入 `scale`，否則會對 TRT 引擎做 8×8 探測而觸發 shape guard 錯誤
- 分段續傳靠 `Decoder(start_time=)` 的 `-ss` 定位，實測與不分段輸出逐幀差 ≤2/255
