---
title: Google GitHub 开发服务规则
area: project
purpose: design
lifecycle: draft
created: 2026-06-17
updated: 2026-06-17
tags:
  - openclash
  - clash
  - rules
  - development
---

# Google / GitHub / 开发服务规则

## 零、项目重写原则

1. **不依赖外部仓库**：所有规则在本项目内自行维护创建，不依赖第三方规则仓库。
2. **按组审查确认**：每一组规则先确认设计，再进入完整配置。
3. **最小可用原则**：只保留必要的规则，不盲目复制大量个人偏好列表。

---

## 一、策略组设计

### 1.1 开发服务统一策略组

所有开发相关服务统一走 `开发服务` 策略组：

```yaml
proxy-groups:
  - name: 开发服务
    type: select
    proxies:
      - 通用选择    # 首选：默认走通用选择，统一节点
      # 其他节点...
```

**推荐默认选「通用选择」**：统一节点选择，切换「通用选择」就切换了所有开发服务的出口。

---

## 二、具体规则设计

### 2.1 Google 全家桶

```yaml
# 主站
- DOMAIN-SUFFIX,google.com,开发服务
- DOMAIN-SUFFIX,google.com.hk,开发服务

# Google 搜索
- DOMAIN-SUFFIX,googleusercontent.com,开发服务

# Gmail
- DOMAIN-SUFFIX,gmail.com,开发服务
- DOMAIN-SUFFIX,googlemail.com,开发服务

# Google Drive / Docs / Sheets / Slides
- DOMAIN-SUFFIX,drive.google.com,开发服务
- DOMAIN-SUFFIX,docs.google.com,开发服务
- DOMAIN-SUFFIX,sheets.google.com,开发服务
- DOMAIN-SUFFIX,slides.google.com,开发服务

# Google Meet
- DOMAIN-SUFFIX,meet.google.com,开发服务

# Google Calendar
- DOMAIN-SUFFIX,calendar.google.com,开发服务

# Google Photos
- DOMAIN-SUFFIX,photos.google.com,开发服务

# Google Maps
- DOMAIN-SUFFIX,maps.google.com,开发服务

# Google Translate
- DOMAIN-SUFFIX,translate.google.com,开发服务

# Google Chrome 同步
- DOMAIN-SUFFIX,chrome.google.com,开发服务
- DOMAIN-SUFFIX,chromestatus.com,开发服务

# Google Cloud
- DOMAIN-SUFFIX,cloud.google.com,开发服务
- DOMAIN-SUFFIX,googleapis.com,开发服务

# ⚠️ 注意：Google Gemini 相关域名已单独分到「AI 服务」策略组
# 因为 Gemini 对节点地区要求更严格，需要可以单独切换

# YouTube（如果希望走单独策略组，可以移到流媒体分组）
- DOMAIN-SUFFIX,youtube.com,开发服务
- DOMAIN-SUFFIX,ytimg.com,开发服务
- DOMAIN-SUFFIX,googlevideo.com,开发服务
```

### 2.2 GitHub 全家桶

```yaml
# 主站
- DOMAIN-SUFFIX,github.com,开发服务

# GitHub Pages
- DOMAIN-SUFFIX,github.io,开发服务

# GitHub CDN
- DOMAIN-SUFFIX,githubusercontent.com,开发服务

# GitHub API
- DOMAIN-SUFFIX,api.github.com,开发服务

# GitHub Actions / Packages / Container Registry
- DOMAIN-SUFFIX,ghcr.io,开发服务
- DOMAIN-SUFFIX,actions.githubusercontent.com,开发服务
- DOMAIN-SUFFIX,packages.githubusercontent.com,开发服务

# GitHub Gist
- DOMAIN-SUFFIX,gist.github.com,开发服务
```

### 2.3 其他开发相关服务

```yaml
# Stack Overflow
- DOMAIN-SUFFIX,stackoverflow.com,开发服务
- DOMAIN-SUFFIX,stackexchange.com,开发服务

# NPM
- DOMAIN-SUFFIX,npmjs.com,开发服务

# PyPI
- DOMAIN-SUFFIX,pypi.org,开发服务
- DOMAIN-SUFFIX,pythonhosted.org,开发服务

# Docker Hub
- DOMAIN-SUFFIX,docker.com,开发服务
- DOMAIN-SUFFIX,docker.io,开发服务

# Rust Crates
- DOMAIN-SUFFIX,crates.io,开发服务

# VS Code
- DOMAIN-SUFFIX,code.visualstudio.com,开发服务
- DOMAIN-SUFFIX,vscode-cdn.net,开发服务

# JetBrains
- DOMAIN-SUFFIX,jetbrains.com,开发服务

# OpenAPI / Swagger
- DOMAIN-SUFFIX,swagger.io,开发服务

# MDN Web Docs
- DOMAIN-SUFFIX,developer.mozilla.org,开发服务
```

---

## 三、规则位置

```yaml
rules:
  # 1. 私有网络（最高优先级）
  # 2. 回家域名（仅手机）
  # 3. 自用直连
  # 4. AI 服务规则
  # 5. 广告/拦截规则
  # 6. ✅ 开发服务规则 ← 在这里
  # 7. 流媒体
  # 8. 游戏
  # 9. 金融
  # 10. 国内直连
  # 11. 兜底
```

---

## 四、注意事项

### 4.1 YouTube 分组问题

当前设计中 YouTube 放在「开发服务」里。如果你更常看视频而不是用 YouTube 做开发，可以：
- 把 YouTube 相关域名移到「流媒体」分组
- 或者保持在开发服务，因为 YouTube 学习视频也是开发的一部分

**本设计默认 YouTube 走开发服务策略组。**

### 4.2 GitHub 加速

如果 GitHub clone 速度慢，可以：
1. 切换到香港或日本节点（物理距离更近）
2. 或者使用国内镜像源（不推荐，可能有安全风险）

建议优先试香港节点，延迟通常比新加坡还低。

### 4.3 新增开发服务的原则

- 只要是日常开发会用到的国外服务，都加进来
- 宁可多一条规则，不要漏一条导致访问慢
- 国内开发服务（如 Gitee）不需要加，会走国内直连

---

## 五、已确认 ✅

本分组已确认（2026-06-17）：

| # | 设计点 |
|---|---------|
| 1 | 所有开发相关服务统一走 `开发服务` 策略组 |
| 2 | `开发服务` 策略组默认推荐新加坡节点 |
| 3 | 规则覆盖：Google 全家桶 + GitHub 全家桶 + 常见开发服务（StackOverflow/NPM/PyPI/Docker等） |
| 4 | Google Gemini 相关域名单独分到「AI 服务」策略组，因为对节点地区要求更严格 |
| 5 | YouTube 默认走开发服务策略组（可根据使用习惯调整） |
| 6 | 规则位置：在广告/拦截规则之后、流媒体之前 |

---

## 六、后续计划

确认本分组后，继续第 6 组：**流媒体**。

---

## 来源

- 项目 README：[[README|OpenClash 规则重写]]
- 项目状态：[[STATUS|OpenClash 规则重写状态]]
