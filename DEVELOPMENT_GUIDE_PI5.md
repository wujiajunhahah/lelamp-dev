# LeLamp Pi 5 Development Guide

这份文档面向这个工作区的维护者，不是面向首次装机用户。

如果你只是想把 Pi 5 一次性配起来，优先看：

- `README.md`
- `HARDWARE_PROFILE_PI5.md`
- `LELAMP_PI5_BRINGUP_CN.md`
- `OPENCLAW_LELAMP_PI5_CN.md`

## 目标

这个仓库的目标不是还原上游，而是把 LeLamp 收成一套适合个人维护的 `Pi 5 + OpenClaw` 工作区。

这里的原则是：

1. 默认只优化 `Pi 5`
2. 默认只安全支持 `ReSpeaker 2-Mics Pi HAT V2.0`
3. 默认把 OpenClaw 当高层远控层，不当低延迟 teleop 引擎
4. 默认让系统 bring-up 可以被一条命令串起来

## 目录职责

### 根目录

- `README.md`
  面向仓库读者的总入口。
- `HARDWARE_PROFILE_PI5.md`
  当前假设的硬件画像。
- `LELAMP_PI5_BRINGUP_CN.md`
  面向装机的中文 bring-up 指南。
- `OPENCLAW_LELAMP_PI5_CN.md`
  面向 OpenClaw 集成的中文说明。
- `DEVELOPMENT_GUIDE_PI5.md`
  当前这份维护文档。
- `site/`
  GitHub Pages 静态站点源文件。
- `host_tools/`
  宿主机侧 pre-OS 辅助脚本和 bootfs 种子脚本。

### `lelamp_runtime/`

- `scripts/pi5_all_in_one.sh`
  当前唯一推荐的一键入口。
- `scripts/pi_setup_max.sh`
  LeLamp runtime 和音频配置层。
- `scripts/openclaw_pi5_setup.sh`
  OpenClaw 安装层。
- `scripts/install_openclaw_skill.sh`
  把 skill 装进 OpenClaw 的本地技能目录。
- `scripts/pi5_post_reboot_finalize.sh`
  重启后自动做 download-files 和设备自检。
- `lelamp/runtime_config.py`
  所有运行时环境变量入口。
- `lelamp/remote_control.py`
  提供给 OpenClaw 调用的安全高层命令。
- `openclaw/skills/lelamp-control/SKILL.md`
  OpenClaw 的 LeLamp 技能定义。

### `host_tools/`

- `pi5_preos_check_macos.sh`
  在 Mac 上检查你有没有准备好官方刷卡路径。
- `pi5_zero_touch_seed.sh`
  把 `userconf.txt`、`ssh`、`firstrun.sh` 和 `lelamp-bootstrap.service` 的首启自举链写进 bootfs。
- `pi5_zero_touch.env.example`
  给 `pi5_zero_touch_seed.sh` 使用的环境模板。

## 一键入口的执行顺序

`pi5_all_in_one.sh` 负责：

1. 识别 Pi 型号、架构、OS codename
2. 拒绝错误平台，除非显式允许
3. 自动检测已有 `.env`、串口、service、OpenClaw
4. 收集安装变量
5. 写入 `.env`
6. 调用 `pi_setup_max.sh`
7. 可选调用 `openclaw_pi5_setup.sh`
8. 安装 LeLamp OpenClaw skill
9. 安装 one-shot post-boot finalizer
10. 跑一遍 `doctor` 快照
11. 引导用户重启

## 音频策略

### 默认策略

- `RESPEAKER_VARIANT=auto`
- 在 `Pi 5` 上默认按 `v2` 走

### 为什么不自动支持 v1

`ReSpeaker V1 / WM8960` 在 `Pi 5 + Bookworm/Trixie` 上不是安全默认路径。  
与其伪装成“全自动兼容”，不如明确拒绝并要求人工确认。

### 如果以后要加 v1

建议新增：

- 单独的 `configure_respeaker_v1_bookworm()` 或 legacy path
- 明确的检测条件
- 单独的 README 说明
- 至少一份在真实设备上的验证记录

## OpenClaw 策略

OpenClaw 在这里是：

- 手机命令入口
- 远程 dashboard 层
- 高层自动化层

OpenClaw 在这里不是：

- 电机底层驱动
- 校准器
- 低延迟遥操作栈

所以 `lelamp.remote_control` 故意只暴露：

- `show-config`
- `list-recordings`
- `play`
- `solid`
- `clear`

不要把 `setup_motors`、`calibrate`、`record` 直接交给 OpenClaw 自动执行，除非你明确知道后果。

## GitHub Pages

站点源代码在：

- `site/index.html`
- `site/developer.html`
- `site/styles.css`

部署工作流在：

- `.github/workflows/pages.yml`

当前 workflow 还额外设置了：

- `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true`

这是为了提前避开 GitHub Actions 的 Node 20 废弃告警。

站点职责：

- 对外解释仓库的目标和硬件画像
- 给到 `stage-0 bootfs 种子` 和 `stage-1 Pi installer` 两个入口
- 给到开发者入口和维护说明

站点不是文档生成器，不做复杂构建，保持纯静态。

## 更新流程建议

当你要继续维护这个仓库时，按这个顺序：

1. 先改脚本或配置
2. 再更新 `README.md`
3. 再更新 `site/index.html` / `site/developer.html`
4. 再更新中文说明文档
5. 最后做 shell 语法检查和 Python 编译检查

## 建议的验证命令

```bash
bash -n host_tools/pi5_preos_check_macos.sh
bash -n host_tools/pi5_zero_touch_seed.sh
bash -n lelamp_runtime/scripts/lelamp_doctor.sh
bash -n lelamp_runtime/scripts/pi_setup_max.sh
bash -n lelamp_runtime/scripts/openclaw_pi5_setup.sh
bash -n lelamp_runtime/scripts/install_openclaw_skill.sh
bash -n lelamp_runtime/scripts/pi5_all_in_one.sh
bash -n lelamp_runtime/scripts/pi5_post_reboot_finalize.sh
python -m compileall lelamp_runtime/lelamp/remote_control.py lelamp_runtime/lelamp/runtime_config.py lelamp_runtime/main.py lelamp_runtime/smooth_animation.py
```
