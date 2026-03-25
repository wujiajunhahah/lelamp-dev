# LeLamp Pi 5 Bring-Up Workspace

这个工作区已经不是原始的上游仓库镜像了，而是按你现在的目标收成了一套 `Pi 5 + LeLamp + OpenClaw` 的落地环境。

目标很明确：

- 你的树莓派到手后尽量只跑一条命令
- 自动判断当前设备是不是 `Pi 5`
- 自动走最安全的 `ReSpeaker` 配置路径
- 自动准备 `LeLamp Runtime`
- 自动准备 `OpenClaw`
- 自动准备 `systemd` 服务和重启后的收尾检查

## GitHub Pages

仓库包含一个纯静态的 GitHub Pages 站点，源文件在 `site/`，部署工作流在 `.github/workflows/pages.yml`。

Pages 的职责是：

- 对外快速解释这套仓库到底做了什么
- 给到一键安装入口
- 给到开发和维护入口

如果仓库开启了 Pages，默认页面就是 `site/index.html`。

## 你的当前硬件画像

详细清单见 [HARDWARE_PROFILE_PI5.md](./HARDWARE_PROFILE_PI5.md)。

当前默认假设是：

- `Raspberry Pi 5`
- `Raspberry Pi OS Lite 64-bit`
- `ReSpeaker 2-Mics Pi HAT V2.0`
- `8x5 WS2812B Matrix`
- `5x STS3215`
- `TTL servo driver`
- `Pi Camera`
- `speaker + microphone`
- `LeLamp 3D prints`

重要修正：

- `Pi 5` 主供电必须按 `5V / 5A USB-C` 处理
- TNKR / BOM 里的 `5V / 2A` 不能当 `Pi 5` 主供电

## 一条命令入口

把仓库放到你的 Pi 上之后，进入 [`lelamp_runtime`](./lelamp_runtime/) 执行：

```bash
cd ~/lelamp_runtime
chmod +x scripts/pi5_all_in_one.sh
./scripts/pi5_all_in_one.sh
```

如果你想全程尽量不交互，也可以提前把变量带进去：

```bash
cd ~/lelamp_runtime
AUTO_ACCEPT_DEFAULTS=1 \
AUTO_REBOOT=1 \
LAMP_ID=lelamp \
LAMP_PORT=/dev/ttyACM0 \
RESPEAKER_VARIANT=auto \
INSTALL_OPENCLAW=1 \
OPENCLAW_INSTALL_MODE=standard \
./scripts/pi5_all_in_one.sh
```

## 这条命令会做什么

总控脚本 [pi5_all_in_one.sh](./lelamp_runtime/scripts/pi5_all_in_one.sh) 会：

1. 检测 `Pi 型号 / OS / 架构`
2. 检测你是不是在 `Pi 5` 路线
3. 写入 `.env`
4. 调用 [pi_setup_max.sh](./lelamp_runtime/scripts/pi_setup_max.sh) 配好 LeLamp runtime
5. 按安全策略处理 `ReSpeaker`
6. 安装可选的 `LeLamp` 开机服务
7. 调用 [openclaw_pi5_setup.sh](./lelamp_runtime/scripts/openclaw_pi5_setup.sh) 安装 OpenClaw
8. 安装 LeLamp 的 OpenClaw skill
9. 安装一个重启后自动收尾的 one-shot service
10. 在重启后自动生成一份设备状态报告

## 自动适配策略

### Pi 版本

- 默认只为 `Pi 5` 收口
- 如果不是 `Pi 5`，脚本会拦住
- 如果你真的要在别的板子上试，显式传 `ALLOW_NON_PI5=1`

### ReSpeaker 版本

- `RESPEAKER_VARIANT=auto`
  默认当成 `V2.0`
- `RESPEAKER_VARIANT=v2`
  直接走安全的 `V2.0` 路线
- `RESPEAKER_VARIANT=v1`
  在 `Pi 5 + Bookworm/Trixie` 上默认拒绝自动配置
- `RESPEAKER_VARIANT=skip`
  完全跳过音频 HAT 配置

这不是保守，是为了避免你在不受支持的 `WM8960 / V1` 路线上踩坑。

## 当前已经准备好的关键文件

- 总控入口: [lelamp_runtime/scripts/pi5_all_in_one.sh](./lelamp_runtime/scripts/pi5_all_in_one.sh)
- LeLamp Pi 配置: [lelamp_runtime/scripts/pi_setup_max.sh](./lelamp_runtime/scripts/pi_setup_max.sh)
- 重启后自动收尾: [lelamp_runtime/scripts/pi5_post_reboot_finalize.sh](./lelamp_runtime/scripts/pi5_post_reboot_finalize.sh)
- OpenClaw 安装: [lelamp_runtime/scripts/openclaw_pi5_setup.sh](./lelamp_runtime/scripts/openclaw_pi5_setup.sh)
- OpenClaw skill 安装: [lelamp_runtime/scripts/install_openclaw_skill.sh](./lelamp_runtime/scripts/install_openclaw_skill.sh)
- OpenClaw 技能: [lelamp_runtime/openclaw/skills/lelamp-control/SKILL.md](./lelamp_runtime/openclaw/skills/lelamp-control/SKILL.md)
- 环境变量模板: [lelamp_runtime/.env.example](./lelamp_runtime/.env.example)
- Pi 5 总说明: [LELAMP_PI5_BRINGUP_CN.md](./LELAMP_PI5_BRINGUP_CN.md)
- OpenClaw 总说明: [OPENCLAW_LELAMP_PI5_CN.md](./OPENCLAW_LELAMP_PI5_CN.md)
- 开发维护文档: [DEVELOPMENT_GUIDE_PI5.md](./DEVELOPMENT_GUIDE_PI5.md)
- Pages 主页: [site/index.html](./site/index.html)
- Pages 开发页: [site/developer.html](./site/developer.html)
- Pages 工作流: [.github/workflows/pages.yml](./.github/workflows/pages.yml)

## 重启后看哪里

重启以后，自动收尾脚本会生成：

- `lelamp_runtime/POST_BOOT_REPORT.md`

这份报告会收集：

- `aplay -l`
- `arecord -l`
- `/dev/ttyACM*`
- `download-files` 结果
- `OpenClaw` 状态检查

## 仍然必须手动做的事情

下面这些东西没有任何脚本能替你真自动完成：

- 实物组装
- 舵机接线
- 首次舵机 ID 配置
- 首次校准时的人手摆位
- 确认你拿到的 `ReSpeaker` 到底是 `V1` 还是 `V2.0`

所以这套方案的定义不是“把物理世界变没”，而是“把软件和系统配置压缩成一条安全路径”。

## 到货后推荐顺序

1. 跑一遍 `./scripts/pi5_all_in_one.sh`
2. 重启
3. 看 `POST_BOOT_REPORT.md`
4. 确认音频设备和串口设备正常
5. 再做舵机 ID 配置和校准
6. 再启用语音 agent
7. 最后再让 OpenClaw 从手机入口接管高层控制

## 上游参考

- LeLamp 文档与硬件: https://tnkr.ai/explore/docs/human-computer-lab/lelamp-v1
- LeLamp Runtime 上游: https://github.com/humancomputerlab/lelamp_runtime
- OpenClaw 文档: https://docs.openclaw.ai/
