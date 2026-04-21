#!/bin/bash
# Mnemos PostToolUse Hook — logs tool outcomes + auto-feeds token signal.
#
# 1. Logs success/failure signal to .mnemos/signals.jsonl (error density)
# 2. If fatigue.json is stale (>60s), estimates context usage from JSONL
#
# Receives JSON on stdin with tool_name, tool_input, tool_response.
# Install: add to .claude/settings.json under hooks.PostToolUse
# Timeout: 1 second max — never blocks

# Skip if no .mnemos directory
if [ ! -d ".mnemos" ]; then
    exit 0
fi

# Read hook input from stdin
HOOK_INPUT=$(cat)

if [ -z "$HOOK_INPUT" ]; then
    exit 0
fi

# Log signal + update fatigue.json if stale
python3 -c "
import json, sys, time, os, glob

try:
    data = json.loads('''$(echo "$HOOK_INPUT" | sed "s/'/'\\\\''/g")''')
except:
    sys.exit(0)

tool = data.get('tool_name', '')
tool_input = data.get('tool_input', {})
response = data.get('tool_response', {})

# Extract file path
fp = tool_input.get('file_path', '') or tool_input.get('path', '')

# Determine success
success = True
if isinstance(response, dict):
    if response.get('error') or response.get('is_error'):
        success = False
    if 'exit_code' in response and response['exit_code'] != 0:
        success = False
elif isinstance(response, str):
    if response.startswith('Error:') or 'error' in response[:50].lower():
        success = False

# Append signal
signal = {
    'tool': tool,
    'event': 'post',
    'file_path': fp,
    'success': success,
    'ts': time.time()
}

os.makedirs('.mnemos', exist_ok=True)
with open('.mnemos/signals.jsonl', 'a') as f:
    f.write(json.dumps(signal) + '\n')

# ─── Auto-feed token signal from JSONL if fatigue.json is stale ───

fatigue_path = '.mnemos/fatigue.json'
stale = True
try:
    with open(fatigue_path) as f:
        fd = json.load(f)
    # Fresh if updated within last 60 seconds (statusline is feeding it)
    if time.time() - fd.get('timestamp', 0) < 60:
        stale = False
except:
    pass

if stale:
    # Find the most recent session JSONL
    home = os.path.expanduser('~')
    cwd = os.getcwd()
    # Claude Code project hash: path with / replaced by -
    project_key = cwd.replace('/', '-')
    if project_key.startswith('-'):
        pass  # expected
    project_dir = os.path.join(home, '.claude', 'projects', project_key)

    if not os.path.isdir(project_dir):
        # Try parent directories (Claude Code may use git root)
        for parent in [os.path.dirname(cwd), os.path.dirname(os.path.dirname(cwd))]:
            pk = parent.replace('/', '-')
            pd = os.path.join(home, '.claude', 'projects', pk)
            if os.path.isdir(pd):
                project_dir = pd
                break

    try:
        jsonl_files = sorted(
            glob.glob(os.path.join(project_dir, '*.jsonl')),
            key=os.path.getmtime, reverse=True
        )
        if jsonl_files:
            # Read the last line of the most recent JSONL
            with open(jsonl_files[0], 'rb') as f:
                # Seek to end, scan backwards for last newline
                f.seek(0, 2)
                pos = f.tell()
                if pos > 0:
                    # Read last 8KB (enough for one JSON entry)
                    read_size = min(8192, pos)
                    f.seek(pos - read_size)
                    chunk = f.read().decode('utf-8', errors='replace')
                    lines = chunk.strip().split('\n')
                    last_line = lines[-1]
                    entry = json.loads(last_line)
                    usage = entry.get('message', {}).get('usage', {})
                    if usage:
                        input_tok = usage.get('input_tokens', 0)
                        cache_read = usage.get('cache_read_input_tokens', 0)
                        cache_create = usage.get('cache_creation_input_tokens', 0)
                        total_in_context = input_tok + cache_read + cache_create
                        # Opus/Sonnet context window = 200k
                        context_limit = 200000
                        # JSONL tokens overestimate actual context by ~25%
                        # due to cache overhead. Apply correction factor.
                        correction = 0.75
                        used_pct = min(100.0, (total_in_context * correction / context_limit) * 100)
                        fatigue_data = {
                            'used_percentage': round(used_pct, 1),
                            'remaining_percentage': round(100 - used_pct, 1),
                            'used_tokens': total_in_context,
                            'total_tokens': context_limit,
                            'remaining_tokens': max(0, context_limit - total_in_context),
                            'timestamp': time.time(),
                            'source': 'jsonl_estimate'
                        }
                        with open(fatigue_path, 'w') as f:
                            json.dump(fatigue_data, f)
    except:
        pass  # Best effort — don't block the hook
"

exit 0
