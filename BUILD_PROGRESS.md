# LeLamp 搭建进度追踪

> 最后更新: 2026-04-10
> 树莓派访问信息、密钥和其他敏感项：见 1Password / 本地私有记录

---

## 总体进度

| 阶段 | 状态 | 预计时间 |
|------|------|----------|
| 0. 前置准备 | ✅ 已完成 | - |
| 1. 3D 打印 | ✅ 已完成 | - |
| 2. 舵机配置 | ✅ 已完成 | - |
| 3. 灯体组装 | ⬜ 待开始 | 1-2 小时 |
| 4. 树莓派软件配置 | ✅ 已完成 | - |
| 5. LED 控制与语音交互 | ✅ 已完成 | - |
| 6. 校准与控制 | ⬜ 待开始 | 30 分钟 |
| 7. 端侧 AI 模型 | ✅ 已完成 | - |

---

## 阶段 0: 前置准备

- [x] 所有元件已采购
- [x] 3D 打印件已打印完成
- [x] 树莓派 5 已刷系统 (Debian 13 trixie, 64-bit)
- [x] SSH 可连接 (`wujiajun@192.168.102.87`)
- [x] 项目代码已部署到树莓派 (`~/lelamp-dev/lelamp_runtime`)

---

## 阶段 2: 舵机配置 (已完成)

### 2.1 在你的 Mac 上配置舵机

> 舵机初始 ID 设置需要在你的电脑（Mac）上完成，不是树莓派上。

**舵机编号对照表：**

| 舵机名称 | 舵机 ID | 位置说明 |
|----------|---------|----------|
| base_yaw | 1 | 底座旋转 |
| base_pitch | 2 | 底座俯仰 |
| elbow_pitch | 3 | 肘部俯仰 |
| wrist_roll | 4 | 手腕旋转 |
| wrist_pitch | 5 | 手腕俯仰 |

**步骤：**

- [x] **给 5 个舵机贴标签** (标记 ID 1-5)
- [x] **Mac 上准备本地 runtime 环境** (端口: `/dev/cu.usbmodem5B140289131`)
- [x] **连接舵机驱动板到 Mac** (USB + 5V/2A DC 供电)
- [x] **运行舵机配置脚本**
  ```bash
  uv run -m lelamp.setup_motors --id lelamp --port /dev/cu.usbmodem5B140289131
  ```
- [x] **全部 5 个舵机 ID 配置成功** (wrist_pitch=5, wrist_roll=4, elbow_pitch=3, base_pitch=2, base_yaw=1)

### 2.2 注意事项

- 每次只连接 **一个** 舵机进行 ID 设置
- 设置完一个后断开，再接下一个
- 灯的名称 `--id lelamp` 要记住，后续所有步骤都会用到

---

## 阶段 3: 灯体组装

### 3.1 头部组装

- [ ] 剥开网线，露出内部单根线
- [ ] 焊接喇叭连接 (黑=GND, 红=5V)
- [ ] 焊接 LED 矩阵连接 (黑=GND, 红=5V, 黄=Data)
- [ ] 喇叭和 LED 放入头部 3D 打印件

### 3.2 底座组装

- [ ] 将舵机驱动板和树莓派固定在底座内
- [ ] USB Type-C 线连接舵机驱动板到树莓派
- [ ] 焊接 ReSpeaker Hat 排针
- [ ] ReSpeaker Hat 连接到树莓派 GPIO
- [ ] 头部网线另一端焊接母排针/JST 连接器
- [ ] 连接到 ReSpeaker Hat 对应引脚

### 3.3 身体（臂体）组装

- [ ] 安装舵机到 3D 打印臂件中 (参考 OnShape 3D 视图)
- [ ] 齿轮角朝外侧安装
- [ ] 菊花链式串联舵机线 (手腕 -> 肘部 -> 底座 -> 驱动板)
- [ ] 如果线不够长，接线延长

### 3.4 供电

- [ ] 5V/2A DC 电源 -> 舵机驱动板
- [ ] 5V/5A USB-C 电源 -> 树莓派 (Pi 5 推荐 5A)

---

## 阶段 4: 树莓派软件配置

### 4.1 已完成部分

- [x] 系统已刷 (Debian 13 trixie)
- [x] SSH 已开启
- [x] Wi-Fi 已连接
- [x] 项目代码已部署到 `~/lelamp-dev/lelamp_runtime`
- [x] ReSpeaker overlay 已配置
- [x] 音频设备已识别 (card 2: seeed2micvoicec)
- [x] asound.conf 已配置
- [x] 用户已加入 dialout/gpio/i2c/spi 组
- [x] uv 已安装 (`~/.local/bin/uv`)
- [x] Python venv 已创建 (`.venv`, Python 3.12)
- [x] 音频依赖已安装 (portaudio19-dev, sounddevice)
- [x] Runtime 依赖已同步

### 4.2 待完成部分

- [x] **扬声器已连接** — 音频输出测试通过，Line 输出已配置
- [ ] **创建 .env 配置文件** (需填入 MODEL_* 和 LIVEKIT_* 密钥)
- [ ] **配置 sudo 的 uv 路径**
- [ ] **测试音频** (扬声器到货后)
- [ ] **测试舵机连接** (组装完成后)

---

## 阶段 5: LED 控制与语音交互

> 完成日期: 2026-04-10

### 5.1 LED 硬件驱动 (已解决)

**问题**: Pi 5 上 `rpi_ws281x` 的 DMA 不兼容，`ws2811_init` 返回 "Out of memory"。

**解决方案**: 使用 Pi 5 官方内核模块 `ws2812-pio`（RP1 PIO 驱动）。

```bash
# 加载 overlay（GPIO 12, 40 LEDs）
sudo dtoverlay ws2812-pio gpio=12 num_leds=40
# 设备节点: /dev/leds0
# 官方驱动用户态像素缓冲: N*4 bytes = RGBW/pad
# 亮度通过单独的 1 byte write 设置
```

**关键发现**:
- LED 矩阵为 8x5 (40 LEDs)，非 8x8
- Pi 5 官方驱动接受 `RGB0` 像素缓冲，亮度是独立通道
- 需要 sudo 权限写入 `/dev/leds0`
- overlay 必须写入 `/boot/firmware/config.txt`，否则重启后会丢

### 5.2 语音控制 LED 程序

**文件**: `~/lelamp-dev/lelamp_runtime/voice_led.py`

**功能**:
- 离线语音识别 (vosk + 中文模型)
- 支持图案: 星星、爱心、笑脸
- 支持颜色: 红/绿/蓝/紫/黄/橙/白/粉/青
- 音量自动控制 LED 亮度
- 说"关灯"关闭

**依赖**:
- `vosk` (venv 中已安装)
- `sounddevice` (venv 中已安装)
- `numpy` (venv 中已安装)
- `vosk-model-cn` 模型 (`~/lelamp-dev/vosk-model-cn/`)

**运行命令**:
```bash
cd ~/lelamp-dev/lelamp_runtime
sudo .venv/bin/python voice_led.py           # 语音控制模式
sudo .venv/bin/python voice_led.py --no-vosk  # 仅音量响应模式
```

**语音指令示例**:
| 语音 | 效果 |
|------|------|
| 紫色星星 | 紫色星星图案 |
| 红色爱心 | 红色爱心图案 |
| 开心 | 黄色笑脸 |
| 蓝色 | 全蓝 |
| 关灯 | 灯灭 |

**注意事项**:
- 麦克风采样率必须为 48kHz (ReSpeaker 不支持 16kHz)
- vosk KaldiRecognizer 也需设为 48kHz

---

## 阶段 7: 端侧 AI 模型

> 完成日期: 2026-04-10

### 7.1 模型信息

| 项目 | 值 |
|------|-----|
| 模型 | Google Gemma 3 4B IT |
| 格式 | GGUF (Q4_K_M 量化) |
| 大小 | ~2.49 GB |
| 路径 | `~/lelamp-dev/models/gemma-3-4b-it-Q4_K_M.gguf` |
| 推理引擎 | llama-cpp-python |
| 线程 | 4 |
| 上下文 | 2048 tokens |

### 7.2 已验证

- [x] 模型可正常加载
- [x] 中文对话测试通过（回复"你好！"）
- [x] 内存占用可接受（8GB Pi 5）

### 7.3 运行方式

```bash
cd ~/lelamp-dev/lelamp_runtime
sudo .venv/bin/python -c "
from llama_cpp import Llama
llm = Llama(model_path='/home/wujiajun/lelamp-dev/models/gemma-3-4b-it-Q4_K_M.gguf',
            n_ctx=2048, n_threads=4, verbose=False)
r = llm.create_chat_completion(
    messages=[{'role':'user','content':'你好'}], max_tokens=50)
print(r['choices'][0]['message']['content'])
"
```

### 7.4 待集成

- [ ] 将 Gemma 模型接入语音控制 LED 程序，替代简单的关键词匹配
- [ ] 实现自然语言理解：用户自由描述需求，模型解析为 LED 指令

---

## 阶段 5: 校准与控制

- [ ] **校准舵机**
  ```bash
  sudo uv run -m lelamp.calibrate --id lelamp --port /dev/ttyACM0
  ```
  > 注意: yaw 轴舵机只旋转 ±90 度，不要全拧！
- [ ] **录制第一个动作**
  ```bash
  sudo uv run -m lelamp.record --id lelamp --port /dev/ttyACM0 --name test_move
  ```
- [ ] **回放动作**
  ```bash
  sudo uv run -m lelamp.replay --id lelamp --port /dev/ttyACM0 --name test_move
  ```
- [ ] **启动语音 Agent** (可选)
  ```bash
  uv run smooth_animation.py console
  ```

---

## 系统信息快照

| 项目 | 值 |
|------|-----|
| 树莓派型号 | Pi 5B rev 1.1 |
| 系统 | Debian 13 (trixie) aarch64 |
| 内核 | 6.12.47+rpt-rpi-2712 |
| Python (venv) | 3.12.13 |
| 磁盘 | 58G (可用 44G) |
| 内存 | 8G (可用 ~7.3G) |
| CPU | 4 核 aarch64 |
| 音频输入 | ReSpeaker 2-Mic V2.0 (card 2, 48kHz) |
| 音频输出 | 扬声器未连接 |
| LED | 8x5 WS2812B Matrix (GPIO 12, /dev/leds0) |
| 网络 | Wi-Fi (192.168.102.87) |
| Tailscale | 已安装运行 |

---

## 已安装的关键软件

| 软件 | 版本/状态 |
|------|-----------|
| uv | 0.11.3 |
| vosk | venv 中已安装 |
| sounddevice | 0.5.2 |
| llama-cpp-python | 0.3.20 |
| numpy | 2.2.6 |
| Gemma 3 4B GGUF | Q4_K_M, 2.49GB |
| vosk-model-small-cn | 0.22, 42MB |

---

## 下一步行动

**优先级排序：**

1. **扬声器已就绪** → 音频输出配置完成 → 可启动完整 AI 语音助手
2. **灯体组装** (阶段 3) → 舵机安装 + 线路连接
3. **将 Gemma 模型接入语音 LED 程序** → 用 LLM 理解自然语言指令控制灯光
4. **舵机校准** (组装完成后)

**可选优化：**
- 将 `ws2812-pio` overlay 写入 `/boot/firmware/config.txt` 实现开机自动加载
- 为 `voice_led.py` 创建 systemd service 实现开机自启
- 添加更多 LED 图案和动画效果

需要帮助随时问我，我可以直接远程操作树莓派。
