# LeLamp Pi 5 极速配置清单

这份清单按你现在这套 `TNKR LeLamp V1` 公开 BOM 来定制，但已经按 `Pi 5` 路线修正，目标是树莓派到手后一次性装好、校准好、跑到稳定状态。

## 你这套 BOM 已确认的关键件

- `Pi 5` 1 个
- `32GB microSD` 1 张
- `ReSpeaker 2-Mics Pi HAT` 1 个
- `8x5 WS2812B Matrix` 1 个
- `STS3215` 舵机 5 个
- `Waveshare TTL Servo Driver` 1 个
- `5V 2A` 电源 1 个
- `Type-C -> Micro USB` 线 1 根
- 薄网线、螺丝、热熔铜柱、跳线、3D 打印件

我已经按这套硬件把运行时默认配置准备成 `Pi 5 + 40 LEDs + ReSpeaker HAT` 路线了。

## 先确认一个版本细节

如果你是最近按 TNKR 这条链路买的 ReSpeaker，大概率拿到的是 `ReSpeaker 2-Mics Pi HAT V2.0`。

- `Pi 5` 我建议只按 `V2.0` 文档走
- 如果你手里其实是老的 `V1/WM8960` 版本，先别照我这份音频步骤直接冲
- 到手时先拍一下 HAT 正反面或者把丝印版本告诉我，我可以立刻帮你分流

## 先改掉一个容易翻车的认知

`Pi 5` 的主供电不要按 BOM 里的 `5V/2A` 去理解。

- `Pi 5` 推荐用独立的 `5V/5A USB-C` 电源
- 如果只用 `5V/3A`，官方文档明确说 USB 外设电流会被限制到 `600mA`
- 你这项目里还有音频帽子、USB 串口舵机驱动、网络和语音推理，所以我建议直接上官方 `27W USB-C` 或等价 `5V/5A` 供电

也就是说，BOM 里的 `5V/2A DC` 更像是项目其余部分的参考供电件，不能拿来当 `Pi 5` 的稳妥主电源。

## 现在就能提前做的事

1. 先准备账号和密钥。
   你至少需要 `OPENAI_API_KEY`、`LIVEKIT_URL`、`LIVEKIT_API_KEY`、`LIVEKIT_API_SECRET`。
2. 把 3D 件和五个舵机贴好标签。
   舵机 ID 对应关系是 `base_yaw=1`、`base_pitch=2`、`elbow_pitch=3`、`wrist_roll=4`、`wrist_pitch=5`。
3. 把这几个文件先看一遍。
   `lelamp_runtime/.env.example`
   `lelamp_runtime/scripts/pi_setup_max.sh`
   `lelamp_runtime/scripts/lelamp.service.example`
4. 确认你打算给树莓派用什么用户名。
   我已经把运行时改成支持 `LELAMP_AUDIO_USER`，不会再写死 `pi`。

## 树莓派到手后的最短路径

1. 用 Raspberry Pi Imager 刷 `Raspberry Pi OS Lite 64-bit`。
   提前勾上 Wi-Fi、SSH、用户名和密码。
2. 首次开机后 SSH 上去，把仓库放到 Pi 上。
   推荐目录 `/home/<你的用户名>/lelamp_runtime`。
3. 在 Pi 上进入仓库根目录，执行：

```bash
chmod +x scripts/pi_setup_max.sh
./scripts/pi_setup_max.sh
```

4. 编辑 `.env`，填入 OpenAI 和 LiveKit 密钥。
5. 重启树莓派。
6. 重启后先确认音频帽子被系统识别：

```bash
aplay -l
arecord -l
```

7. 然后再跑一次模型/资源下载：

```bash
uv run smooth_animation.py download-files
```

8. 按这个顺序验机：
   `uv run -m lelamp.test.test_audio`
   `sudo uv run -m lelamp.test.test_rgb`
   `uv run lerobot-find-port`
   `uv run -m lelamp.setup_motors --id <lamp_id> --port <port>`
   `uv run -m lelamp.calibrate --id <lamp_id> --port <port>`
   `uv run -m lelamp.test.test_motors --id <lamp_id> --port <port>`

9. 最后再启动语音 Agent：

```bash
uv run smooth_animation.py console
```

## 我已经替你预先做好的改动

- `main.py` 和 `smooth_animation.py` 不需要再手改灯 ID 和串口了，直接读 `.env`
- LED 数量已经统一成 `40`，匹配你这套 `8x5 WS2812B Matrix`
- 音量控制用户不再写死 `pi`
- 额外补了 `.env.example`
- 额外补了 Pi 一键准备脚本
- 额外补了 systemd 服务模板

## 建议你到时候这样冲到“配置到极致”

1. 默认直接用 `smooth_animation.py`，比离散回放更自然。
2. `Pi 5` 先把供电拉满。
   独立 `5V/5A USB-C` 电源优先级高于一切软件调优。
3. 所有硬件测试都单项跑通以后，再开 LiveKit 语音。
4. 第一次别急着开机自启。
   先手动 `console` 跑通，再启用 service。
5. 校准时最容易出事的是两个 yaw 轴。
   只做中心点两侧小范围摆动，不要暴力全拧。
6. 语音、灯光、舵机三者里，最容易卡你的是音频 overlay 和串口识别。
   所以我建议你把注意力先放在 `aplay -l` 和 `lerobot-find-port`。

## 我建议你现场给我回传的第一批信息

- `aplay -l`
- `arecord -l`
- `uv run lerobot-find-port`
- `ls /dev/ttyACM*`
- `.env` 里除密钥外的配置
- 你 Pi 的用户名

这样你树莓派一到手，我们可以直接进入排障和调优，不再回头补基础配置。
