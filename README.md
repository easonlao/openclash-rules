---
title: OpenClash 规则重写
area: project
purpose: guide
lifecycle: active
created: 2026-06-16
updated: 2026-06-16
tags:
  - openclash
  - clash
  - rules
---

# OpenClash 规则重写

## 目标

把当前使用的 Clash/OpenClash 模板重写成更可控的结构：

- 默认走一个“通用选择”总控。
- 国内和私有网络保持直连。
- 特殊服务可单独切换节点。
- 后续可插入链式代理开关。
- 每一组规则先确认，再进入完整配置草稿。

## 参考来源

- 当前模板：`C:\Users\eason\.codex\attachments\2248a3c7-6a70-47cc-a7cd-dcd1364bd5c9\pasted-text.txt`
- liandu2024 自定义列表缓存：`C:\tmp\liandu2024-clash-lists\`
- Mihomo 官方规则说明：`https://wiki.metacubex.one/en/config/rules/`
- Mihomo 官方示例配置：`https://wiki.metacubex.one/en/example/conf/`
- MetaCubeX 规则库：`https://github.com/MetaCubeX/meta-rules-dat`

## 重写顺序

1. 基础策略组与通用选择
2. 国内、私有网络、自用直连
3. 广告/拦截规则
4. AI 服务
5. Google / GitHub / 开发服务
6. 流媒体
7. 游戏
8. 金融 / 加密货币
9. 测试 / IP 检测
10. 链式代理开关
11. 最终兜底规则

## 当前判断

当前模板的 `RULE-SET` 引用关系是完整的，没有发现启用规则指向不存在的 provider 或策略组。

主要需要改的是结构：

- `default` 第一项是 `直连`，会导致多数业务组默认直连。
- `国内` 继承 `default`，后续加通用选择时应拆成独立组。
- `Block / Domain` 不是通用广告规则，只是 Adobe 相关阻断列表。
- liandu2024 的 `Direct.list` 包含大量机场、订阅、VPN 和 VPS 域名，属于作者个人偏好，不宜不加审查地全盘沿用。
- `Direct.list` 与 `Proxy.list` 有一个冲突域名：`v140oy1s.xyz`。
