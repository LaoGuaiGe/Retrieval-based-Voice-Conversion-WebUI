# RVC 实时变声部署文档

> **开源地址：** https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI
> **目标：** 男声→女声实时变声，用于游戏语音（CF 穿越火线等）
> **日期：** 2026-06-28
> **硬件：** RTX 4070 12GB / Windows 11

---

## 一、环境信息

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.10.11 | `C:\Program Files\Python310\` |
| PyTorch | 2.5.1+cu121 | CUDA 12.1 |
| CUDA Driver | 13.2 | 向下兼容 |
| fairseq | 0.12.2 | 需修改 setup.py 跳过 C 扩展编译 |
| gradio | 3.34.0 | Web 界面 |
| gradio_client | 0.2.10 | 兼容版本 |
| FreeSimpleGUI | 5.2.0 | 实时变声 GUI |

---

## 二、安装步骤

### 1. 安装 Python 3.10

```bash
# 下载安装包
curl -L "https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe" -o python-installer.exe
# 静默安装（需管理员）
python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1
```

### 2. 安装 PyTorch

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 3. 安装 fairseq（跳过 C 扩展）

fairseq 的 C 扩展仅用于 BLEU 计算，RVC 不需要。需先修改 setup.py：

```python
# setup.py 中修改两处
ext_modules=[]   # 原为 ext_modules=extensions
pass # cmdclass disabled  # 原为 cmdclass["build_ext"] = ...
```

然后安装：
```bash
pip install fairseq==0.12.2 --no-build-isolation
```

### 4. 安装项目依赖

```bash
pip install -r requirements.txt
pip install FreeSimpleGUI sounddevice noisereduce flask flask_cors
```

---

## 三、模型文件

### 基础模型（必需）

| 文件 | 大小 | 路径 |
|------|------|------|
| hubert_base.pt | 181 MB | `assets/hubert/` |
| rmvpe.pt | 173 MB | `assets/rmvpe/` |

下载来源：`https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/`

### 声音模型（中文女声）

| 文件名 | 音色 | 用途 |
|--------|------|------|
| `yalin_yujie.pth` + `.index` | 御姐音 | ⭐ 推荐首选 |
| `wanxin.pth` + `.index` | 温柔女声 | 备选 |
| `shiyun.pth` + `.index` | 清晰女声 | 备选 |
| `xuejie.pth` + `.index` | 少女音 | 备选 |

下载来源：`https://huggingface.co/chaye741/RVC-Voice-Models/resolve/main/`

> ⚠️ **注意：** 模型文件名不能包含中文，需改为拼音

---

## 四、启动方式

### 实时变声 GUI

```batch
go-realtime-gui.bat
```

或在终端中：

```bash
"C:\Program Files\Python310\python.exe" gui_v1.py
```

### Web 训练/推理界面

```batch
go-web.bat
```

---

## 五、实时变声参数配置

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| PTH 路径 | `assets/weights/yalin_yujie.pth` | 声音模型 |
| Index 路径 | `assets/weights/yalin_yujie.index` | 特征索引 |
| 音高 (Pitch) | `+12` | 男→女关键参数 |
| Index Rate | `0.75` | 音色相似度 |
| F0 算法 | `rmvpe` | 效果最好 |
| 半精度 | ☑ 开启 | 加速推理 |
| Block Time | `0.13s` | 延迟参数 |
| 输入设备 | 物理麦克风 | 如：麦克风 (2- M590Q) |
| 输出设备 | CABLE Input | VB-Audio Virtual Cable |

---

## 六、游戏音频路由（CF 穿越火线）

### 原理

```
物理麦克风 → RVC 变声 → CABLE Input ═(虚拟线)═ CABLE Output(系统默认麦克风) → CF 自动读取
```

### 配置步骤

1. **安装 VB-Cable**：https://vb-audio.com/Cable/
2. **设置系统默认麦克风**：Win+R → `mmsys.cpl` → 录制 → 右键 CABLE Output → 设为默认设备
3. **RVC 输出**：选择 CABLE Input
4. **启动游戏**：CF 自动使用系统默认麦克风（CABLE Output）

### 监听自己声音（可选）

1. Win+R → `mmsys.cpl` → 录制
2. 右键 CABLE Output → 属性 → 侦听
3. ☑ 侦听此设备 → 播放设备选你的耳机

---

## 七、已修复的启动脚本

### go-realtime-gui.bat

```batch
"C:\Program Files\Python310\python.exe" gui_v1.py
pause
```

### go-web.bat

```batch
"C:\Program Files\Python310\python.exe" infer-web.py --pycmd "C:\Program Files\Python310\python.exe" --port 7897
pause
```

> 原脚本依赖不存在的 `runtime\python.exe`，已改为系统 Python 路径。

---

## 八、故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| `ImportError: media_data from gradio_client` | gradio/gradio_client 版本不匹配 | `pip install gradio_client==0.2.10` |
| `ModuleNotFoundError: fairseq` | 未安装或编译失败 | 按第三节方法修改 setup.py 后重装 |
| `RuntimeError: An attempt has been made to start a new process` | Windows multiprocessing 限制 | 仅通过 GUI 启动，不直接 import rtrvc |
| 模型路径有中文 | FreeSimpleGUI 不支持中文路径 | 改为拼音文件名 |
| 游戏没声音输出 | 默认播放设备被改了 | 检查 mmsys.cpl 播放设备设置 |
| 变声效果不自然 | 音高不合适 | 在 +10 ~ +14 之间微调 |

---

## 九、关键文件路径

```
Retrieval-based-Voice-Conversion-WebUI/
├── gui_v1.py                    # 实时变声 GUI 主程序
├── infer-web.py                 # Web 训练/推理界面
├── go-realtime-gui.bat          # 实时变声启动脚本
├── go-web.bat                   # Web 界面启动脚本
├── infer/lib/rtrvc.py           # 实时推理引擎
├── configs/config.py            # 配置文件（GPU/精度等）
├── assets/
│   ├── hubert/hubert_base.pt    # 特征提取模型
│   ├── rmvpe/rmvpe.pt           # 音高提取模型
│   └── weights/
│       ├── yalin_yujie.pth      # 雅琳御姐（御姐音）
│       ├── yalin_yujie.index
│       ├── wanxin.pth           # 婉心（温柔女声）
│       ├── wanxin.index
│       ├── shiyun.pth           # 诗韵（清晰女声）
│       ├── shiyun.index
│       ├── xuejie.pth           # 学姐（少女音）
│       └── xuejie.index
└── requirements.txt             # Python 依赖列表
```
