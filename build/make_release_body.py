"""產生 GitHub Release 的 JSON body（避免 shell 反引號插值）。"""
import json
from pathlib import Path

NOTES = """本机影片画质增强工具，超分到 4K、补帧到 60/120fps，断点续传。

## 适合谁

- Windows 10/11 64-bit
- **NVIDIA 独立显卡**（AMD 版尚未发布；无独显无法使用）
- 不需要管理员权限安装

## 下载与合并（重要）

安装包 3.8 GB，超过 GitHub 单文件 2 GB 上限，拆成两卷。两个文件都要下载到**同一个资料夹**，然后合并：

1. 下载 `VideoEnhance_NVIDIA_v1.0.0_setup.part1`（约 1.90 GB）
2. 下载 `VideoEnhance_NVIDIA_v1.0.0_setup.part2`（约 1.81 GB）
3. 在该资料夹打开命令提示字符，执行：

    copy /B VideoEnhance_NVIDIA_v1.0.0_setup.part1+VideoEnhance_NVIDIA_v1.0.0_setup.part2 VideoEnhance_NVIDIA_v1.0.0_setup.exe

4. 双击生成的 `VideoEnhance_NVIDIA_v1.0.0_setup.exe` 安装

合并后的 SHA256：21943690c27d533a9494d475833a315e0ef9cbe865fe904bc9aa15fcc5b03ec7

## 第一次启动

1. 选输出资料夹（只问一次，之后记住）
2. 扫描设备 → 列出六个模型让你确认 → 下载约 178 MB（需联网）
3. 进主界面后把影片拖进去，选素材类型（实拍／动画）与画质，勾选超分／补帧，按开始

## 说明

- torch、ffmpeg 已打包进安装档，不用另外装 Python 或环境
- 模型不在安装包内，首次启动才下载，来源为 GitHub / Hugging Face
- 没有数位签章，SmartScreen 会警告「未知发行者」，选「其他资讯 → 仍要执行」
- 移除安装不会删除已下载的模型（%LOCALAPPDATA%\\VideoEnhance\\models）

源码与详细文件说明见仓库 README。
"""

BODY = {
    "tag_name": "v1.0.0",
    "name": "Video Enhance 1.0.0 (NVIDIA)",
    "body": NOTES,
    "draft": False,
    "prerelease": False,
}

if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "release_body.json"
    out.write_text(json.dumps(BODY, ensure_ascii=False), encoding="utf-8")
    print(out)
