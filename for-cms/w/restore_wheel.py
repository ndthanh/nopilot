import argparse
import hashlib
import json
from pathlib import Path
import struct

HEADER = b'WHEELJPEG1:H:'
DATA = b'WHEELJPEG1:D:'


def read_part(path):
    blob = path.read_bytes()
    if blob[:2] != b'\xff\xd8':
        raise ValueError(f'{path}: not a JPEG')
    pos, meta, chunks = 2, None, []
    while pos < len(blob):
        if blob[pos] != 255:
            raise ValueError(f'{path}: invalid JPEG marker')
        while pos < len(blob) and blob[pos] == 255:
            pos += 1
        marker = blob[pos]
        pos += 1
        if marker in (0xDA, 0xD9):
            break
        if pos + 2 > len(blob):
            raise ValueError('Truncated segment')
        size = struct.unpack('>H', blob[pos:pos + 2])[0]
        if size < 2 or pos + size > len(blob):
            raise ValueError('Invalid segment length')
        payload = blob[pos + 2:pos + size]
        pos += size
        if marker == 0xEF and payload.startswith(HEADER):
            if meta is not None:
                raise ValueError('Duplicate header')
            meta = json.loads(payload[len(HEADER):])
        elif marker == 0xEF and payload.startswith(DATA):
            chunks.append(payload[len(DATA):])
    if meta is None:
        raise ValueError(f'{path}: wheel metadata missing')
    data = b''.join(chunks)
    if len(data) != meta['part_size'] or hashlib.sha256(data).hexdigest() != meta['part_sha256']:
        raise ValueError(f'{path}: data corrupted or metadata stripped')
    return meta, data


def restore(paths, out_dir):
    parts = [read_part(p) for p in paths]
    parts.sort(key=lambda item: item[0]['part'])
    first = parts[0][0]
    if len(parts) != 2 or [m['part'] for m, _ in parts] != [1, 2]:
        raise ValueError('Exactly two distinct parts (1 and 2) are required')
    for meta, _ in parts:
        if meta['total'] != 2 or any(meta[k] != first[k] for k in ('filename', 'size', 'sha256')):
            raise ValueError('Parts belong to different files')
    filename = first['filename']
    if '/' in filename or '\\' in filename or ':' in filename or not filename.endswith('.whl'):
        raise ValueError('Invalid output filename')
    data = b''.join(d for _, d in parts)
    if len(data) != first['size'] or hashlib.sha256(data).hexdigest() != first['sha256']:
        raise ValueError('Final SHA-256 or size mismatch')
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / filename
    # Never overwrite an existing file.
    with target.open('xb') as handle:
        handle.write(data)
    print(f'Restored: {target.resolve()}')
    print(f'Size: {len(data)} bytes')
    print(f'SHA-256: {first["sha256"]}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parts', type=Path, nargs=2)
    parser.add_argument('--out', type=Path, default=Path('.'))
    args = parser.parse_args()
    try:
        restore(args.parts, args.out)
    except (ValueError, OSError, KeyError, IndexError, struct.error) as exc:
        parser.exit(1, f'Error: {exc}\n')
