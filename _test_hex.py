"""验证 hex 解析逻辑"""
import sys, os
sys.path.insert(0, '.')
os.environ['PYTHONIOENCODING'] = 'utf-8'
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def parse_hex(s):
    cleaned = s.replace(' ', '').replace('\t', '').replace('\n', '')
    if cleaned.startswith('0x') or cleaned.startswith('\\x'):
        raise ValueError('不可以以 0x 或 \\x 开头')
    if len(cleaned) % 2 != 0 and cleaned:
        raise ValueError(f'hex 字符串长度 {len(cleaned)} 不是 2 的倍数')
    if not cleaned:
        return b''
    return bytes.fromhex(cleaned)


# 测试样例
tests = [
    ('FF D8 FF', b'\xff\xd8\xff'),
    ('ff d8 ff', b'\xff\xd8\xff'),
    ('FFD8FF', b'\xff\xd8\xff'),
    ('', b''),
    ('00 00', b'\x00\x00'),
]
for s, expected in tests:
    r = parse_hex(s)
    ok = 'OK' if r == expected else 'FAIL'
    print(f'{s!r:20s} -> {r.hex().upper():10s} | {ok}')

# 错误案例
errors = ['0xFF', '\\xFF', 'FF D8 F', 'XYZ']
for s in errors:
    try:
        parse_hex(s)
        print(f'{s!r:20s} -> 应该报错但没报!')
    except ValueError as e:
        print(f'{s!r:20s} -> {e}')