#!/usr/bin/env python3
"""
OpenClash 配置文件验证脚本
用于检测配置文件的语法、引用、URL、锚点格式等问题

格式规则：
- .mrs 文件（二进制）+ behavior=domain → 需要 *domain 锚点
- .mrs 文件（二进制）+ behavior=ipcidr → 需要 *ip 锚点
- .list 文件（纯文本）+ behavior=classical → 需要 *class 锚点
"""

import yaml
import requests
import sys
import re
from urllib.parse import urlparse

def validate_config(filename='config_local.yaml'):
    print("=" * 60)
    print(f"验证配置文件: {filename}")
    print("=" * 60)
    
    errors = []
    warnings = []
    
    # 1. YAML 语法检查
    print("\n[1/9] YAML 语法检查...")
    try:
        with open(filename, 'r') as f:
            config = yaml.safe_load(f)
        print("  ✅ YAML 语法正确")
    except yaml.YAMLError as e:
        print(f"  ❌ YAML 语法错误: {e}")
        errors.append(f"YAML 语法错误: {e}")
        return errors, warnings
    
    # 2. 顶级字段检查
    print("\n[2/9] 顶级字段检查...")
    required_fields = ['mixed-port', 'allow-lan', 'mode', 'dns', 'proxies', 
                       'proxy-providers', 'proxy-groups', 'rule-providers', 'rules']
    for field in required_fields:
        if field not in config:
            print(f"  ❌ 缺失字段: {field}")
            errors.append(f"缺失字段: {field}")
        else:
            print(f"  ✅ {field}")
    
    # 3. 重复规则集名称检查
    print("\n[3/9] 重复规则集名称检查...")
    if 'rule-providers' in config:
        provider_names = list(config['rule-providers'].keys())
        duplicates = set([x for x in provider_names if provider_names.count(x) > 1])
        if duplicates:
            print(f"  ❌ 发现重复的规则集名称: {duplicates}")
            errors.append(f"重复的规则集名称: {duplicates}")
        else:
            print(f"  ✅ 无重复名称（共 {len(provider_names)} 个规则集）")
    
    # 4. 策略组引用顺序检查
    print("\n[4/9] 策略组引用顺序检查...")
    if 'proxy-groups' in config:
        group_names = [g['name'] for g in config['proxy-groups']]
        order_errors = []
        for i, g in enumerate(config['proxy-groups']):
            if 'proxies' in g:
                for ref in g['proxies']:
                    # 跳过节点名和直连/拒绝
                    if ref in ['直连', '拒绝', 'DIRECT', 'REJECT']:
                        continue
                    if ref in group_names and group_names.index(ref) > i:
                        order_errors.append(f"'{g['name']}' 引用的 '{ref}' 定义在后面")
        
        if order_errors:
            print(f"  ❌ 发现 {len(order_errors)} 个引用顺序错误:")
            for e in order_errors[:5]:
                print(f"    - {e}")
            errors.extend(order_errors)
        else:
            print(f"  ✅ 所有策略组引用顺序正确")
    
    # 5. 规则集与规则引用匹配检查
    print("\n[5/9] 规则集与规则引用匹配检查...")
    if 'rule-providers' in config and 'rules' in config:
        provider_names = set(config['rule-providers'].keys())
        referenced_names = set()
        
        for rule in config['rules']:
            if isinstance(rule, str) and 'RULE-SET,' in rule:
                parts = rule.split(',')
                if len(parts) >= 2:
                    referenced_names.add(parts[1])
        
        missing_refs = []
        for ref in referenced_names:
            if ref not in provider_names:
                missing_refs.append(ref)
        
        if missing_refs:
            print(f"  ❌ 发现 {len(missing_refs)} 个引用不存在的规则集:")
            for ref in missing_refs[:5]:
                print(f"    - {ref}")
            errors.extend(missing_refs)
        else:
            print(f"  ✅ 所有 {len(referenced_names)} 个引用都匹配")
    
    # 6. 规则集命名格式检查
    print("\n[6/9] 规则集命名格式检查...")
    if 'rule-providers' in config:
        bad_names = []
        for name in config['rule-providers'].keys():
            if not (' / Domain' in name or ' / IP' in name):
                bad_names.append(name)
        
        if bad_names:
            print(f"  ⚠️  发现 {len(bad_names)} 个规则集名称不符合 'Name / Domain' 格式:")
            for name in bad_names[:5]:
                print(f"    - {name}")
            warnings.extend(bad_names)
        else:
            print(f"  ✅ 所有规则集名称格式正确")
    
    # 7. 策略组引用检查
    print("\n[7/9] 策略组引用检查...")
    if 'proxy-groups' in config:
        all_group_names = set(g['name'] for g in config['proxy-groups'])
        all_proxy_names = set()
        if 'proxies' in config:
            all_proxy_names = set(p['name'] for p in config['proxies'])
        
        valid_names = all_group_names | all_proxy_names | {'直连', '拒绝', 'DIRECT', 'REJECT'}
        
        ref_errors = []
        for g in config['proxy-groups']:
            if 'proxies' in g:
                for ref in g['proxies']:
                    if ref not in valid_names and not ref.startswith('DIRECT') and not ref.startswith('REJECT'):
                        ref_errors.append(f"'{g['name']}' 引用了不存在的 '{ref}'")
        
        if ref_errors:
            print(f"  ❌ 发现 {len(ref_errors)} 个无效引用:")
            for e in ref_errors[:5]:
                print(f"    - {e}")
            errors.extend(ref_errors)
        else:
            print(f"  ✅ 所有策略组引用有效")
    
    # 8. 规则集锚点格式检查（核心检查）
    print("\n[8/9] 规则集锚点格式检查...")
    if 'rule-providers' in config:
        anchor_errors = []
        
        for name, rule in config['rule-providers'].items():
            if not isinstance(rule, dict) or 'url' not in rule:
                continue
            
            url = rule['url']
            behavior = rule.get('behavior', '')
            format_type = rule.get('format', '')
            
            # 核心规则：
            # .mrs 文件（二进制）+ behavior=domain → 需要 *domain 锚点
            # .mrs 文件（二进制）+ behavior=ipcidr → 需要 *ip 锚点
            # .list 文件（纯文本）+ behavior=classical → 需要 *class 锚点
            
            is_mrs = '.mrs' in url
            is_list = '.list' in url
            
            if is_mrs:
                # .mrs 文件必须用 mrs 格式
                if format_type != 'mrs':
                    anchor_errors.append(
                        f"{name}: .mrs 文件 format 必须是 mrs，当前: format={format_type}"
                    )
                # behavior 必须是 domain 或 ipcidr
                if behavior == 'domain':
                    # 这是正确的
                    pass
                elif behavior == 'ipcidr':
                    # 这是正确的（IP 类型）
                    pass
                else:
                    anchor_errors.append(
                        f"{name}: .mrs 文件 behavior 必须是 domain 或 ipcidr，当前: behavior={behavior}"
                    )
            elif is_list:
                # .list 文件必须用 classical + text
                if behavior != 'classical' or format_type != 'text':
                    anchor_errors.append(
                        f"{name}: .list 文件必须用 *class 锚点（behavior: classical, format: text），"
                        f"当前: behavior={behavior}, format={format_type}"
                    )
        
        if anchor_errors:
            print(f"  ❌ 发现 {len(anchor_errors)} 个锚点格式错误:")
            for e in anchor_errors:
                print(f"    - {e}")
            errors.extend(anchor_errors)
        else:
            print(f"  ✅ 所有规则集锚点格式正确")
    
    # 9. 规则集 URL 可访问性检查（可选，较慢）
    print("\n[9/9] 规则集 URL 可访问性检查...")
    if 'rule-providers' in config:
        url_errors = []
        url_count = 0
        
        for name, rule in config['rule-providers'].items():
            if isinstance(rule, dict) and 'url' in rule:
                url = rule['url']
                url_count += 1
                # 跳过本地文件
                if url.startswith('file:'):
                    continue
                try:
                    response = requests.head(url, timeout=5, allow_redirects=True)
                    if response.status_code != 200:
                        url_errors.append(f"{name}: HTTP {response.status_code}")
                except Exception as e:
                    url_errors.append(f"{name}: {str(e)[:50]}")
        
        if url_errors:
            print(f"  ⚠️  发现 {len(url_errors)} 个 URL 无法访问:")
            for e in url_errors[:5]:
                print(f"    - {e}")
            warnings.extend(url_errors)
        else:
            print(f"  ✅ 所有 {url_count} 个 URL 可访问")
    
    # 总结
    print("\n" + "=" * 60)
    print("验证结果总结")
    print("=" * 60)
    
    if errors:
        print(f"❌ 发现 {len(errors)} 个错误，必须修复:")
        for i, e in enumerate(errors[:10], 1):
            print(f"  {i}. {e}")
        if len(errors) > 10:
            print(f"  ... 还有 {len(errors) - 10} 个错误")
    else:
        print("✅ 无错误")
    
    if warnings:
        print(f"\n⚠️  发现 {len(warnings)} 个警告（可选修复）:")
        for i, w in enumerate(warnings[:10], 1):
            print(f"  {i}. {w}")
        if len(warnings) > 10:
            print(f"  ... 还有 {len(warnings) - 10} 个警告")
    else:
        print("✅ 无警告")
    
    return errors, warnings

if __name__ == '__main__':
    filename = sys.argv[1] if len(sys.argv) > 1 else 'config_local.yaml'
    errors, warnings = validate_config(filename)
    
    # 返回非零退出码表示有错误
    sys.exit(1 if errors else 0)
