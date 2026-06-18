#!/usr/bin/env python3
"""
OpenClash 配置文件发布前验证脚本
检测配置文件的语法、引用、URL、锚点格式等问题。
任何 ERROR 级别问题都会阻止发布（exit 1）。

格式规则：
- .mrs 文件（二进制）+ behavior=domain  → format=mrs, *domain 锚点
- .mrs 文件（二进制）+ behavior=ipcidr  → format=mrs, *ip 锚点
- .list 文件（纯文本）+ behavior=classical → format=text, *class 锚点
"""

import yaml
import requests
import sys
import re
import argparse
from urllib.parse import urlparse


def load_config(filename):
    """加载并解析 YAML 配置文件"""
    try:
        with open(filename, 'r') as f:
            return yaml.safe_load(f), None
    except yaml.YAMLError as e:
        return None, str(e)


def extract_rule_refs(rules):
    """从 rules 列表中提取所有 RULE-SET 引用名"""
    refs = set()
    for rule in rules:
        if isinstance(rule, str) and 'RULE-SET,' in rule:
            parts = rule.split(',')
            if len(parts) >= 2:
                refs.add(parts[1].strip())
    return refs


def check_yaml_syntax(config, errors):
    """检查 1: YAML 语法"""
    if config is None:
        errors.append("YAML 语法错误")
        return False
    return True


def check_required_fields(config, errors):
    """检查 2: 必需的顶级字段"""
    required = ['mixed-port', 'allow-lan', 'mode', 'dns', 'proxies',
                'proxy-providers', 'proxy-groups', 'rule-providers', 'rules']
    for field in required:
        if field not in config:
            errors.append(f"缺失顶级字段: {field}")


def check_duplicate_providers(config, errors):
    """检查 3: 重复的规则集名称"""
    providers = config.get('rule-providers', {})
    names = list(providers.keys())
    dupes = {n for n in names if names.count(n) > 1}
    for d in sorted(dupes):
        errors.append(f"重复规则集名称: {d}")


def check_group_order(config, errors):
    """检查 4: 策略组引用顺序（被引用的组必须先定义）"""
    groups = config.get('proxy-groups', [])
    group_names = [g['name'] for g in groups]
    for i, g in enumerate(groups):
        for ref in g.get('proxies', []):
            if ref in ['直连', '拒绝', 'DIRECT', 'REJECT']:
                continue
            if ref in group_names and group_names.index(ref) > i:
                errors.append(f"策略组顺序错误: '{g['name']}' 引用 '{ref}'，但 '{ref}' 定义在后面")


def check_group_refs(config, errors):
    """检查 5: 策略组中引用的代理/组是否存在"""
    groups = config.get('proxy-groups', [])
    all_group_names = {g['name'] for g in groups}
    all_proxy_names = set()
    for p in config.get('proxies', []):
        if isinstance(p, dict) and 'name' in p:
            all_proxy_names.add(p['name'])

    valid = all_group_names | all_proxy_names | {'直连', '拒绝', 'DIRECT', 'REJECT'}
    for g in groups:
        for ref in g.get('proxies', []):
            if ref not in valid and not ref.startswith('DIRECT') and not ref.startswith('REJECT'):
                errors.append(f"策略组 '{g['name']}' 引用了不存在的 '{ref}'")


def check_provider_naming(config, errors):
    """检查 6: 规则集命名格式必须为 'Name / Domain' 或 'Name / IP'"""
    providers = config.get('rule-providers', {})
    for name in providers:
        if ' / Domain' not in name and ' / IP' not in name:
            errors.append(f"命名格式错误: '{name}'（应为 'Name / Domain' 或 'Name / IP'）")


def check_anchor_format(config, errors):
    """检查 7: 锚点格式一致性（核心规则）
    - .mrs + domain  → format=mrs, behavior=domain
    - .mrs + ipcidr  → format=mrs, behavior=ipcidr
    - .list          → format=text, behavior=classical
    """
    providers = config.get('rule-providers', {})
    for name, rule in providers.items():
        if not isinstance(rule, dict) or 'url' not in rule:
            continue
        url = rule['url']
        behavior = rule.get('behavior', '')
        fmt = rule.get('format', '')
        is_mrs = '.mrs' in url
        is_list = '.list' in url

        if is_mrs:
            if fmt != 'mrs':
                errors.append(f"锚点格式: '{name}' 是 .mrs 文件，format 应为 mrs（当前: {fmt}）")
            if behavior not in ('domain', 'ipcidr'):
                errors.append(f"锚点格式: '{name}' 是 .mrs 文件，behavior 应为 domain 或 ipcidr（当前: {behavior}）")
        elif is_list:
            if behavior != 'classical' or fmt != 'text':
                errors.append(f"锚点格式: '{name}' 是 .list 文件，应为 behavior=classical, format=text（当前: behavior={behavior}, format={fmt}）")


def check_anchor_mismatch(config, errors):
    """检查 8: 名称中的 Domain/IP 与 behavior 是否匹配（仅 .mrs 文件）
    .list 文件 behavior=classical 是固定的，Domain/IP 只表示规则内容类型。
    .mrs 文件必须：/ Domain → behavior=domain，/ IP → behavior=ipcidr。
    """
    providers = config.get('rule-providers', {})
    for name, rule in providers.items():
        if not isinstance(rule, dict) or 'url' not in rule:
            continue
        url = rule['url']
        if '.mrs' not in url:
            continue  # .list 文件跳过，classical 行为固定
        behavior = rule.get('behavior', '')
        if ' / IP' in name and behavior != 'ipcidr':
            errors.append(f"名称/行为不匹配: '{name}' 含 / IP 但 behavior={behavior}（.mrs 文件必须为 ipcidr）")
        if ' / Domain' in name and behavior != 'domain':
            errors.append(f"名称/行为不匹配: '{name}' 含 / Domain 但 behavior={behavior}（.mrs 文件必须为 domain）")


def check_unreferenced_providers(config, errors):
    """检查 9: 规则集定义但未被 rules 引用（孤立规则集）"""
    providers = config.get('rule-providers', {})
    rules = config.get('rules', [])
    refs = extract_rule_refs(rules)
    unreferenced = set(providers.keys()) - refs
    for name in sorted(unreferenced):
        errors.append(f"孤立规则集: '{name}' 已定义但未被 rules 引用")


def check_dangling_refs(config, errors):
    """检查 10: rules 中引用的规则集是否都已定义"""
    providers = config.get('rule-providers', {})
    rules = config.get('rules', [])
    refs = extract_rule_refs(rules)
    dangling = refs - set(providers.keys())
    for name in sorted(dangling):
        errors.append(f"悬空引用: rules 引用了 '{name}' 但 rule-providers 中未定义")


def check_url_accessibility(config, warnings, timeout=5):
    """检查 11: URL 可访问性（仅警告，不阻断）"""
    providers = config.get('rule-providers', {})
    checked = 0
    for name, rule in providers.items():
        if not isinstance(rule, dict) or 'url' not in rule:
            continue
        url = rule['url']
        if url.startswith('file:'):
            continue
        checked += 1
        try:
            resp = requests.head(url, timeout=timeout, allow_redirects=True)
            if resp.status_code != 200:
                warnings.append(f"URL 不可达: '{name}' → HTTP {resp.status_code}")
        except Exception as e:
            warnings.append(f"URL 不可达: '{name}' → {str(e)[:60]}")
    return checked


def check_trailing_whitespace(config, warnings):
    """检查 12: 配置中常见的 YAML 写法问题（仅警告）"""
    # 这个需要读原始文本
    pass


def validate_config(filename, skip_url_check=False, url_timeout=5):
    """运行所有验证检查"""
    print("=" * 60)
    print(f"验证配置文件: {filename}")
    print("=" * 60)

    errors = []
    warnings = []

    # 加载配置
    config, parse_err = load_config(filename)
    if not check_yaml_syntax(config, errors):
        print(f"\n❌ YAML 语法错误:\n  {parse_err}")
        return errors, warnings

    # 运行所有检查
    checks = [
        ("必需字段", check_required_fields),
        ("重复规则集", check_duplicate_providers),
        ("策略组引用顺序", check_group_order),
        ("策略组引用有效性", check_group_refs),
        ("规则集命名格式", check_provider_naming),
        ("锚点格式一致性", check_anchor_format),
        ("名称/行为匹配", check_anchor_mismatch),
        ("孤立规则集", check_unreferenced_providers),
        ("悬空引用", check_dangling_refs),
    ]

    for i, (desc, fn) in enumerate(checks, 1):
        before = len(errors)
        print(f"\n[{i}/{len(checks) + (1 if not skip_url_check else 0)}] {desc}...", end=" ")
        fn(config, errors)
        if len(errors) == before:
            print("✅")
        else:
            print(f"❌ +{len(errors) - before}")

    # URL 检查（可选，较慢）
    if not skip_url_check:
        idx = len(checks) + 1
        print(f"\n[{idx}/{len(checks) + 1}] URL 可访问性...", end=" ")
        checked = check_url_accessibility(config, warnings, url_timeout)
        print(f"✅ 已检查 {checked} 个 URL（{len(warnings)} 个警告）")

    # 总结
    print("\n" + "=" * 60)
    print("验证结果")
    print("=" * 60)

    if errors:
        print(f"\n❌ {len(errors)} 个错误（必须修复，不能发布）:")
        for i, e in enumerate(errors, 1):
            print(f"  {i}. {e}")
    else:
        print("\n✅ 无错误，可以发布")

    if warnings:
        print(f"\n⚠️  {len(warnings)} 个警告（建议修复）:")
        for i, w in enumerate(warnings, 1):
            print(f"  {i}. {w}")

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description='OpenClash 配置文件验证')
    parser.add_argument('files', nargs='*', default=['config_local.yaml', 'config_mobile.yaml'],
                        help='要验证的配置文件（默认: config_local.yaml config_mobile.yaml）')
    parser.add_argument('--skip-url', action='store_true', help='跳过 URL 可访问性检查')
    parser.add_argument('--url-timeout', type=int, default=5, help='URL 检查超时秒数')
    args = parser.parse_args()

    all_errors = []
    all_warnings = []

    for filename in args.files:
        errors, warnings = validate_config(filename, skip_url_check=args.skip_url,
                                           url_timeout=args.url_timeout)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        print()

    # 最终结论
    if len(args.files) > 1:
        print("=" * 60)
        print(f"总计: {len(all_errors)} 个错误, {len(all_warnings)} 个警告")
        if all_errors:
            print("❌ 发布前必须修复所有错误")
        else:
            print("✅ 所有检查通过，可以发布")
        print("=" * 60)

    sys.exit(1 if all_errors else 0)


if __name__ == '__main__':
    main()
