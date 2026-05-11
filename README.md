# endcord-vim

A vim navigation extension for [endcord](https://github.com/SparkLost/endcord), a Discord TUI client.

Requires `vim_mode: true` in your endcord config.

## Installation

Copy `endcord_vim.py` into your endcord extensions directory:

```
~/.config/endcord/Extensions/endcord_vim/endcord_vim.py
```

## Features

All bindings are active in **normal mode** only (press `Escape` to return to normal mode, `i` or `a` to enter insert mode).

---

### Insert mode

| Key | Action |
|-----|--------|
| `i` | Enter insert mode at cursor |
| `a` | Enter insert mode after cursor (appends a space if at end of buffer) |
| `Escape` | Return to normal mode |

---

### Count prefix

Most motion and scroll commands accept a count prefix. Accumulate digits while holding the `switch_tab_modifier` key (default `Alt`), then press a motion key.

Examples: `Alt+5` then `j` scrolls down 5 messages; `Alt+3` then `k` scrolls up 3.

---

### Chat navigation

| Key | Action |
|-----|--------|
| `j` | Scroll down one message |
| `k` | Scroll up one message |
| `Ctrl+D` | Scroll down half a page |
| `Ctrl+U` | Scroll up half a page |
| `zz` | Reposition selected message to center |
| `zt` | Reposition selected message to top |
| `zb` | Reposition selected message to bottom |

Ctrl+U/D skip over blank image placeholder lines inserted by image extensions.

---

### Channel tree navigation

| Key | Action |
|-----|--------|
| `J` | Move down one channel |
| `K` | Move up one channel |
| `ZJ` | Scroll down half a page in the tree |
| `ZK` | Scroll up half a page in the tree |
| `ZZ` | Reposition selected channel to center |
| `ZT` | Reposition selected channel to top |
| `ZB` | Reposition selected channel to bottom |
| `ZC` | Collapse all servers and folders |

---

### Input line editing (normal mode)

**Cursor motion**

| Key | Action |
|-----|--------|
| `w` | Move to start of next word |
| `b` | Move to start of current/previous word |
| `e` | Move to end of current/next word |
| `$` | Move to end of line |
| `^` | Move to first non-space character |

**Editing**

| Key | Action |
|-----|--------|
| `x` | Delete character under cursor (supports count: `3x`) |
| `dw` | Delete to start of next word |
| `db` | Delete to start of previous word |
| `de` | Delete to end of word |
| `d$` | Delete to end of line |
| `d^` | Delete to first non-space character |
| `diw` | Delete inner word (word chars only, no surrounding spaces) |
| `daw` | Delete a word (word + one adjacent space) |
| `dd` | Delete all text in the input buffer |
| `dm` | Delete the selected message (triggers endcord's confirmation prompt) |
| `cw` | Delete to start of next word and enter insert mode |
| `cb` | Delete to start of previous word and enter insert mode |
| `ce` | Delete to end of word and enter insert mode |
| `c$` | Delete to end of line and enter insert mode |
| `c^` | Delete to first non-space and enter insert mode |
| `ciw` | Delete inner word and enter insert mode |
| `caw` | Delete a word (+ adjacent space) and enter insert mode |
| `cc` | Clear input buffer and enter insert mode |

**Count with `d`/`c`:** place a count before the operator, after it, or both — they multiply.  
Examples: `2dw`, `d3w`, `2d3w` (deletes 6 words); same with `c`.

---

### Marks

Marks let you bookmark messages and jump back to them.

| Key | Action |
|-----|--------|
| `m{a-z}` | Set a local mark (per channel) on the selected message |
| `m{A-Z}` | Set a global mark (across channels) on the selected message |
| `'{a-z}` | Jump to channel of mark and scroll to bottom |
| `'{A-Z}` | Jump to channel of mark and scroll to bottom |
| `` `{a-z} `` | Jump to the exact message the mark is on |
| `` `{A-Z} `` | Jump to the exact message the mark is on (switches channel if needed) |

Marks are saved to `vim_marks.json` next to the extension file and persist across restarts.

---

### Channel tree search

| Key | Action |
|-----|--------|
| `/` | Open incremental search prompt |
| `Backspace` | Remove last character from query |
| `Enter` | Confirm selection and exit search |
| `Escape` | Cancel search and restore original position |
| `n` | (outside search) Go to next match of last query |
| `N` | (outside search) Go to previous match of last query |

While the search prompt is open, typing filters by channel/guild/DM name (case-insensitive substring). The status line shows `/<query>  [match / total]`. After confirming, press `Enter` again (tree select) to open the highlighted channel. `n`/`N` outside the prompt repeat the last query and scroll the tree to show the match.

---

### Other

| Key | Action |
|-----|--------|
| `y` | Yank (copy) the selected message text to clipboard |
| `u` | Upload file (remaps the default `Ctrl+U` upload to `u` in normal mode) |
| `Q` | Quit endcord |

---

## License

GPLv3 — see source file header.
