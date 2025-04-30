# tg-sync

`tg-sync` downloads Telegram Media files, according to configuration. Features:
- _incremental mode_: starts processing from the point, where it stopped previously
- _live mode_: listens to new messages
- supports multiple chats and accounts
- supports various media types: `photo`, `video`, `voice`, `document`, etc.
- supports custom download locations

Minimal `tg-sync` command line looks like this:
```bash
tg-sync.py -c config.yaml -a account-dir
```
Option `-c` (`--config`) specifies path to global configuration file. Option `-a`  (`--account`) specifies path to account working directory. Account working directory should contain file `account.yaml`  with account settings and credentials:
```yaml
id: My account
api_id: 12345678
api_hash: abcdefghijklmnopqrstuvwxyz
phone: +1234567890
```

Also account working directory will contain account session database, temporary download location and other stuff like this.
You can specify multiple account working directories.

Global configuration file contains description of processing pipeline and other global options.

```yaml
processing:
- filters:
  - chat_id: 12345678
    type_id: [photo, video, voice]
  actions:
  - action: save
    save_path: '/mnt/archive/Telegram/{date:%Y}/{date:%Y%m%d-%H%M%S}-{type_id}-{message_id}.{ext}'
```

This simple configuration will save all photo and video files of specified chat into specified location. More complex pipelines can be set up to meet your needs.

### Processing pipeline

Each message produces event, which passes through pipeline. Event is a dict with the following keys:
```python
message_id: int
account_id: str
chat_id: int
chat_type: str
chat_title: str
chat_login: str
chat_fullname: str
user_id: int
user_login: str
user_fullname: str
type_id: str
date: datetime
```

Processing pipeline consists of steps, executed sequentially. Each steps defines `filters` (optional) and `actions` (required). If `filters` are present, event should match at least one of filters to execute `actions`.

Each filter consists of keys and expected values: either scalar value, or list. If event matches all filter keys, then filter is matched (and executes following actions).

There are several predefined actions:
- `set` - sets new fields to event
- `save` - saves message media
- `exit` - exits processing pipeline

For example, the following pipeline saves photo and video from two chats into custom locations:

```yaml
- filters:
  - chat_id: 12345678
  actions:
  - action: set
    chat_name: Family
- filters:
  - chat_id: 34567890
  actions:
  - action: set
    chat_name: Friends
- filters:
  - chat_name: [Family, Friends]
    type_id: [photo, video]
  actions:
  - action: save
    save_path: './Telegram/{date:%Y}/{chat_name}/{date:%Y%m%d-%H%M%S}-{type_id}-{message_id}.{ext}'
```

Action `exit` can be used to filter events out of pipeline:
```yaml
- filters:
  - chat_id: 12345678
  actions:
  - action: exit
# process rest
```
