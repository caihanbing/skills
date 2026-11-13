"""Validate newline-delimited CodeFree-O events and identify the session."""
import argparse
import json
import sys


def parse_events(lines, expected=None):
    sessions = set()
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError('invalid JSON event') from exc
        if not isinstance(event, dict):
            raise ValueError('event is not an object')
        if event.get('type') == 'error':
            raise ValueError('error event')
        sid = event.get('sessionID')
        if sid is not None:
            if not isinstance(sid, str) or not sid.strip():
                raise ValueError('invalid session ID')
            sessions.add(sid)
    if len(sessions) != 1:
        raise ValueError('missing or inconsistent session ID')
    sid = next(iter(sessions))
    if expected is not None and sid != expected:
        raise ValueError('session ID differs from requested session')
    return sid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('events')
    parser.add_argument('--session')
    args = parser.parse_args()
    try:
        with open(args.events, encoding='utf-8') as stream:
            sid = parse_events(stream, args.session)
    except (OSError, ValueError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({'ok': True, 'sessionID': sid}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
