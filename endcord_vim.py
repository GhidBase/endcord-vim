# Copyright (C) 2025-2026 Dylan Simon
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.

"""Vim navigation: count-prefix j/k/J/K, Ctrl+U/D half-page, zt/zz/zb reposition, m/'/` marks, e/b/w/$//^ word motion, d operator."""

import json
import logging
import os

EXT_NAME = "Vim Navigation"
EXT_VERSION = "0.13.0"
EXT_ENDCORD_VERSION = "1.4.2"
EXT_DESCRIPTION = "Vim-style navigation: count prefix, half/page scroll for chat+tree, zt/zz/zb/ZT/ZZ/ZB, marks."
EXT_SOURCE = "https://github.com/ghidbase/endcord-vim"

logger = logging.getLogger(__name__)

_VIM_DIGIT_CODE = 1001   # action code returned when a digit is absorbed into vim_count
_VIM_SCROLL_CODE = 1002  # action code returned when a handled key should not propagate
_CTRL_U = 21
_CTRL_D = 4
_MARKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vim_marks.json")


class Extension:
    def __init__(self, app):
        self.app = app
        app.tui.vim_count = 0
        app.tui.common_keybindings = self._common_keybindings
        self._marks = self._load_marks()
        logger.info("Vim navigation active")

    # ── marks persistence ────────────────────────────────────────────────────

    def _load_marks(self):
        try:
            with open(_MARKS_FILE, "r") as f:
                data = json.load(f)
            if "local" not in data:
                data["local"] = {}
            if "global" not in data:
                data["global"] = {}
            return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {"local": {}, "global": {}}

    def _save_marks(self):
        try:
            with open(_MARKS_FILE, "w") as f:
                json.dump(self._marks, f, indent=2)
        except OSError as e:
            logger.error(f"vim marks: could not save: {e}")

    # ── mark set / jump ───────────────────────────────────────────────────────

    def _set_mark(self, letter):
        app = self.app
        chat_sel = app.tui.chat_selected
        if chat_sel < 0 or not app.messages:
            app.update_extra_line("vim: no message selected for mark", timed=True)
            return
        msg_index = app.lines_to_msg(chat_sel)
        if msg_index is None:
            app.update_extra_line("vim: cursor not on a message", timed=True)
            return
        message_id = app.messages[msg_index]["id"]

        if letter.islower():
            channel_id = str(app.active_channel["channel_id"])
            if channel_id not in self._marks["local"]:
                self._marks["local"][channel_id] = {}
            self._marks["local"][channel_id][letter] = message_id
        else:
            self._marks["global"][letter] = {
                "channel_id": str(app.active_channel["channel_id"]),
                "channel_name": app.active_channel["channel_name"],
                "guild_id": str(app.active_channel["guild_id"]),
                "guild_name": app.active_channel["guild_name"],
                "message_id": message_id,
            }
        self._save_marks()
        app.update_extra_line(f"vim: mark '{letter}' set", timed=True)

    def _scroll_to_message(self, message_id):
        app = self.app
        tui = app.tui
        msg_index = next(
            (i for i, m in enumerate(app.messages) if m.get("id") == message_id),
            None,
        )
        if msg_index is None:
            return
        target_line = next(
            (i for i, lm in enumerate(app.chat_map) if lm and lm[0] == msg_index),
            None,
        )
        if target_line is None:
            return
        tui.chat_selected = target_line
        h = tui.chat_hw[0]
        max_idx = len(tui.chat_buffer) - h + 2
        tui.chat_index = max(0, min(target_line - h + 1 + h // 2, max_idx))
        tui.draw_chat()

    def _skip_image_placeholders(self, tui, direction):
        """After a scroll lands on blank image placeholder lines, walk direction until a real line."""
        chat_map = self.app.chat_map
        buf = tui.chat_buffer
        limit = len(buf)
        max_idx = limit - tui.chat_hw[0] + 2
        while 0 <= tui.chat_selected < limit:
            lm = chat_map[tui.chat_selected] if tui.chat_selected < len(chat_map) else None
            if lm is not None or (tui.chat_selected < limit and buf[tui.chat_selected].strip()):
                break  # real message line or date separator — stop
            tui.chat_selected += direction
            tui.chat_index = max(0, min(tui.chat_index + direction, max_idx))

    def _collapse_all(self):
        app = self.app
        collapsed = [0] if 0 in app.state["collapsed"] else []
        for obj in app.tree_metadata:
            if obj and obj["type"] < 0 and obj["id"] not in collapsed:
                collapsed.append(obj["id"])
        app.update_tree(collapsed=collapsed)

    # ── input word-motion helpers ─────────────────────────────────────────────

    def _word_forward(self, buf, idx):
        """Vim 'w': skip current word chars, then skip spaces → start of next word."""
        while idx < len(buf) and buf[idx] != ' ':
            idx += 1
        while idx < len(buf) and buf[idx] == ' ':
            idx += 1
        return idx

    def _word_backward(self, buf, idx):
        """Vim 'b': go to start of current or previous word (matches tui.py word_left)."""
        left_len = 0
        for word in buf[:idx].split(" ")[::-1]:
            if word == "":
                left_len += 1
            else:
                left_len += len(word)
                break
        return max(0, idx - left_len)

    def _word_end(self, buf, idx):
        """Vim 'e': go to end of current word, or end of next word if already at end."""
        if idx < len(buf):
            if idx + 1 >= len(buf) or buf[idx + 1] == ' ' or buf[idx] == ' ':
                idx += 1
            while idx < len(buf) and buf[idx] == ' ':
                idx += 1
            while idx + 1 < len(buf) and buf[idx + 1] != ' ':
                idx += 1
        return idx

    def _apply_input_motion(self, tui, new_idx):
        """Set cursor to new_idx, update scroll + cursor_pos, and redraw input."""
        buf = tui.input_buffer
        _, w = tui.input_hw
        tui.input_index = new_idx
        # clamp scroll to valid range for current buffer (important after deletion)
        tui.input_line_index = max(0, min(tui.input_line_index, max(0, len(buf) - w)))
        # scroll right if cursor is past the right edge
        diff_r = tui.input_index - max(0, len(buf) - w - tui.input_line_index) - w
        if diff_r >= 0:
            tui.input_line_index -= diff_r + 4
            tui.input_line_index = min(max(0, tui.input_line_index), max(0, len(buf) - w))
        # scroll left if cursor is before the left edge
        diff_l = tui.input_index - max(0, len(buf) - w + 1 - tui.input_line_index)
        if diff_l <= 0:
            tui.input_line_index -= diff_l - 4
            tui.input_line_index = min(max(0, tui.input_line_index), max(0, len(buf) - w))
        tui.cursor_pos = tui.input_index - max(0, len(buf) - w + 1 - tui.input_line_index)
        tui.cursor_pos = max(0, tui.cursor_pos)
        tui.cursor_pos = min(w - 1, tui.cursor_pos)
        tui.input_select_start = None
        tui.spellcheck()
        tui.draw_input_line()

    # ── mark set / jump ───────────────────────────────────────────────────────

    def _switch_to_mark_channel(self, mark):
        """Switch to the channel stored in a global mark if not already there."""
        app = self.app
        if str(mark["channel_id"]) != str(app.active_channel["channel_id"]):
            app.switch_channel(
                mark["channel_id"], mark["channel_name"],
                mark["guild_id"], mark["guild_name"],
            )
            app.reset_states(replying=True)
            app.update_status_line()

    def _jump_mark_bottom(self, letter):
        """' + letter: go to the channel the mark is in and scroll to bottom."""
        app = self.app
        if letter.islower():
            channel_id = str(app.active_channel["channel_id"])
            if not self._marks["local"].get(channel_id, {}).get(letter):
                app.update_extra_line(f"vim: mark '{letter}' not set", timed=True)
                return
            app.tui.scroll_bot()
        else:
            mark = self._marks["global"].get(letter)
            if not mark:
                app.update_extra_line(f"vim: mark '{letter}' not set", timed=True)
                return
            self._switch_to_mark_channel(mark)
            app.tui.scroll_bot()

    def _jump_mark_exact(self, letter):
        """` + letter: jump to the exact message the mark is on."""
        app = self.app
        if letter.islower():
            channel_id = str(app.active_channel["channel_id"])
            message_id = self._marks["local"].get(channel_id, {}).get(letter)
            if not message_id:
                app.update_extra_line(f"vim: mark '{letter}' not set", timed=True)
                return
            self._scroll_to_message(message_id)
        else:
            mark = self._marks["global"].get(letter)
            if not mark:
                app.update_extra_line(f"vim: mark '{letter}' not set", timed=True)
                return
            self._switch_to_mark_channel(mark)
            self._scroll_to_message(mark["message_id"])

    # ── extension hooks ───────────────────────────────────────────────────────

    def on_binding(self, key, is_command, is_forum):
        """Absorb digit keypresses into vim_count; remap u to upload."""
        tui = self.app.tui

        if (not tui.insert_mode
                and tui.switch_tab_modifier
                and isinstance(key, int)
                and ((49 <= key <= 57) or (key == 48 and tui.vim_count > 0))):
            tui.vim_count = min(tui.vim_count * 10 + (key - 48), 999)
            return _VIM_DIGIT_CODE

        if not tui.insert_mode and key == ord('u') and not is_forum:
            tui.enable_autocomplete = True
            tui.misspelled = []
            return 13   # upload action code

    def on_escape_key(self):
        self.app.tui.vim_count = 0

    def on_wait_input(self, action_code, input_text, chat_sel, tree_sel):
        """Keep the input loop running after a digit or handled scroll."""
        if action_code in (_VIM_DIGIT_CODE, _VIM_SCROLL_CODE):
            self.app.restore_input_text = (input_text, "standard")
            return True

    # ── keybindings replacement ───────────────────────────────────────────────

    def _common_keybindings(self, key, mouse=False, switch=False, command=False, forum=False):
        """Replacement for tui.common_keybindings with vim_count and extra bindings."""
        tui = self.app.tui
        count = max(1, tui.vim_count)
        tui.vim_count = 0

        if key in tui.KEYBINDINGS_CHAT_UP:
            if command:
                return 46
            for _ in range(count):
                if tui.chat_selected + 1 < len(tui.chat_buffer):
                    top_line = tui.chat_index + tui.chat_hw[0] - 3
                    if top_line + 3 < len(tui.chat_buffer) and tui.chat_selected >= top_line:
                        tui.chat_index += 1
                    tui.chat_selected += 1
                else:
                    break
            tui.draw_chat()

        if key in tui.KEYBINDINGS_CHAT_DOWN:
            if command:
                return 47
            for _ in range(count):
                if tui.chat_selected >= tui.dont_hide_chat_selection:
                    if tui.chat_index and tui.chat_selected <= tui.chat_index + 2:
                        tui.chat_index -= 1
                    tui.chat_selected -= 1
                else:
                    break
            tui.draw_chat()

        elif key in tui.keybindings["tree_up"]:
            for _ in range(count):
                if tui.tree_selected >= 0:
                    if tui.tree_index and tui.tree_selected <= tui.tree_index + 2:
                        tui.tree_index -= 1
                    tui.tree_selected -= 1
                elif tui.wrap_around and count == 1:
                    tree_end_index = tui.get_tree_index(0)
                    tui.tree_selected = tree_end_index
                    tui.tree_index = max(tui.tree_selected - (tui.tree_hw[0] - 1), 0)
                    break
                else:
                    break
            tui.draw_tree()

        elif key in tui.keybindings["tree_down"]:
            for _ in range(count):
                if tui.tree_selected + 1 < tui.tree_clean_len:
                    top_line = tui.tree_index + tui.tree_hw[0]
                    if top_line < tui.tree_clean_len and tui.tree_selected >= top_line - 3:
                        tui.tree_index += 1
                    tui.tree_selected += 1
                elif tui.wrap_around and count == 1:
                    tui.tree_selected = 0
                    tui.tree_index = 0
                    break
                else:
                    break
            tui.draw_tree()

        elif key in tui.keybindings["tree_select"]:
            if 300 <= tui.tree_format[tui.tree_selected_abs] <= 399 and not mouse:
                return 4
            if tui.tree_selected_abs == 0 and not switch:
                if (tui.tree_format[tui.tree_selected_abs] % 10):
                    tui.tree_format[tui.tree_selected_abs] -= 1
                else:
                    tui.tree_format[tui.tree_selected_abs] += 1
                tui.draw_tree()
            elif 100 <= tui.tree_format[tui.tree_selected_abs] <= 199 and not switch:
                return 19
            elif 400 <= tui.tree_format[tui.tree_selected_abs] <= 599 and not mouse:
                return 4
            elif tui.tree_selected_abs >= 0 and not switch:
                if (tui.tree_format[tui.tree_selected_abs] % 10):
                    tui.tree_format[tui.tree_selected_abs] -= 1
                else:
                    tui.tree_format[tui.tree_selected_abs] += 1
                tui.draw_tree()
            tui.tree_format_changed = True

        elif key in tui.keybindings["extra_up"]:
            if tui.extra_window_body and not mouse:
                if tui.extra_select:
                    if tui.extra_selected > 0:
                        if tui.extra_index and tui.extra_selected <= tui.extra_index:
                            tui.extra_index -= 1
                        tui.extra_selected -= 1
                        tui.draw_extra_window(tui.extra_window_title, tui.extra_window_body, select=tui.extra_select, reset_scroll=False)
                    elif tui.wrap_around and not tui.wrap_around_disable:
                        tui.extra_selected = len(tui.extra_window_body) - 1
                        tui.extra_index = max(len(tui.extra_window_body) - (tui.win_extra_window.getmaxyx()[0] - 1), 0)
                        tui.draw_extra_window(tui.extra_window_title, tui.extra_window_body, select=tui.extra_select, reset_scroll=False)
                elif tui.extra_index > 0:
                    tui.extra_index -= 1
                    tui.draw_extra_window(tui.extra_window_title, tui.extra_window_body, select=tui.extra_select, reset_scroll=False)
            elif tui.win_member_list:
                if tui.mlist_selected >= 0:
                    if tui.mlist_index and tui.mlist_selected <= tui.mlist_index:
                        tui.mlist_index -= 1
                    tui.mlist_selected -= 1
                    tui.draw_member_list(tui.member_list, tui.member_list_format)
                elif tui.mlist_index > 0:
                    tui.mlist_index -= 1
                    tui.draw_member_list(tui.member_list, tui.member_list_format)

        elif key in tui.keybindings["extra_down"]:
            if tui.extra_window_body and not mouse:
                if tui.extra_select:
                    if tui.extra_selected + 1 < len(tui.extra_window_body):
                        top_line = tui.extra_index + tui.win_extra_window.getmaxyx()[0] - 1
                        if top_line < len(tui.extra_window_body) and tui.extra_selected >= top_line - 1:
                            tui.extra_index += 1
                        tui.extra_selected += 1
                        tui.draw_extra_window(tui.extra_window_title, tui.extra_window_body, select=tui.extra_select, reset_scroll=False)
                    elif tui.wrap_around and not tui.wrap_around_disable:
                        tui.extra_selected = 0
                        tui.extra_index = 0
                        tui.draw_extra_window(tui.extra_window_title, tui.extra_window_body, select=tui.extra_select, reset_scroll=False)
                elif tui.extra_index + 1 < len(tui.extra_window_body):
                    tui.extra_index += 1
                    tui.draw_extra_window(tui.extra_window_title, tui.extra_window_body, select=tui.extra_select, reset_scroll=False)
            elif tui.win_member_list:
                if tui.mlist_selected + 1 < len(tui.member_list):
                    top_line = tui.mlist_index + tui.win_member_list.getmaxyx()[0] - 1
                    if top_line < len(tui.member_list) and tui.mlist_selected >= top_line - 1:
                        tui.mlist_index += 1
                    tui.mlist_selected += 1
                    tui.draw_member_list(tui.member_list, tui.member_list_format)

        elif key == ord('z') and not tui.insert_mode:
            tui.screen.timeout(-1)
            next_key = tui.screen.getch()
            tui.screen.timeout(200)
            if tui.chat_selected >= 0 and next_key in (ord('t'), ord('z'), ord('b')):
                sel = tui.chat_selected
                h = tui.chat_hw[0]
                max_idx = len(tui.chat_buffer) - h + 2
                if next_key == ord('t'):
                    tui.chat_index = max(0, min(sel - h + 1, max_idx))
                elif next_key == ord('z'):
                    tui.chat_index = max(0, min(sel - h + 1 + h // 2, max_idx))
                elif next_key == ord('b'):
                    tui.chat_index = max(0, min(sel, max_idx))
                tui.draw_chat()
            return _VIM_SCROLL_CODE

        elif key == ord('Z') and not tui.insert_mode:
            tui.screen.timeout(-1)
            next_key = tui.screen.getch()
            tui.screen.timeout(200)
            if tui.tree_selected >= 0:
                h = tui.tree_hw[0]
                max_idx = max(0, tui.tree_clean_len - h)
                if next_key in (ord('T'), ord('Z'), ord('B')):
                    sel = tui.tree_selected
                    if next_key == ord('T'):
                        tui.tree_index = max(0, min(sel, max_idx))
                    elif next_key == ord('Z'):
                        tui.tree_index = max(0, min(sel - h // 2, max_idx))
                    elif next_key == ord('B'):
                        tui.tree_index = max(0, min(sel - h + 1, max_idx))
                    tui.draw_tree()
                elif next_key == ord('K'):
                    half = h // 2
                    for _ in range(half):
                        if tui.tree_selected > 0:
                            if tui.tree_index and tui.tree_selected <= tui.tree_index + 2:
                                tui.tree_index -= 1
                            tui.tree_selected -= 1
                        else:
                            break
                    tui.draw_tree()
                elif next_key == ord('J'):
                    half = h // 2
                    for _ in range(half):
                        if tui.tree_selected + 1 < tui.tree_clean_len:
                            top_line = tui.tree_index + h
                            if top_line < tui.tree_clean_len and tui.tree_selected >= top_line - 3:
                                tui.tree_index += 1
                            tui.tree_selected += 1
                        else:
                            break
                    tui.draw_tree()
                elif next_key == ord('C'):
                    self._collapse_all()
            return _VIM_SCROLL_CODE

        elif key == ord('m') and not tui.insert_mode:
            tui.screen.timeout(-1)
            next_key = tui.screen.getch()
            tui.screen.timeout(200)
            if 97 <= next_key <= 122 or 65 <= next_key <= 90:
                self._set_mark(chr(next_key))
            return _VIM_SCROLL_CODE

        elif key == ord("'") and not tui.insert_mode:
            tui.screen.timeout(-1)
            next_key = tui.screen.getch()
            tui.screen.timeout(200)
            if 97 <= next_key <= 122 or 65 <= next_key <= 90:
                self._jump_mark_bottom(chr(next_key))
            return _VIM_SCROLL_CODE

        elif key == ord('`') and not tui.insert_mode:
            tui.screen.timeout(-1)
            next_key = tui.screen.getch()
            tui.screen.timeout(200)
            if 97 <= next_key <= 122 or 65 <= next_key <= 90:
                self._jump_mark_exact(chr(next_key))
            return _VIM_SCROLL_CODE

        elif key in tui.keybindings["word_right"] and not tui.insert_mode:
            # override tui.py's word_right to land on start of next word (not the space before it)
            buf = tui.input_buffer
            self._apply_input_motion(tui, self._word_forward(buf, tui.input_index))
            return _VIM_SCROLL_CODE

        elif key == ord('e') and not tui.insert_mode:
            buf = tui.input_buffer
            self._apply_input_motion(tui, self._word_end(buf, tui.input_index))
            return _VIM_SCROLL_CODE

        elif key == ord('$') and not tui.insert_mode:
            self._apply_input_motion(tui, len(tui.input_buffer))
            return _VIM_SCROLL_CODE

        elif key == ord('^') and not tui.insert_mode:
            buf = tui.input_buffer
            idx = 0
            while idx < len(buf) and buf[idx] == ' ':
                idx += 1
            self._apply_input_motion(tui, idx)
            return _VIM_SCROLL_CODE

        elif key == ord('d') and not tui.insert_mode:
            tui.screen.timeout(-1)
            next_key = tui.screen.getch()
            tui.screen.timeout(200)
            # optional inner count (e.g. d2w)
            inner_count = 0
            while ord('1') <= next_key <= ord('9') or (next_key == ord('0') and inner_count > 0):
                inner_count = inner_count * 10 + (next_key - ord('0'))
                tui.screen.timeout(-1)
                next_key = tui.screen.getch()
                tui.screen.timeout(200)
            n = count * max(1, inner_count)
            buf = tui.input_buffer
            start = tui.input_index
            end = start
            for _ in range(n):
                if next_key in tui.keybindings["word_right"] or next_key == ord('w'):
                    end = self._word_forward(buf, end)
                elif next_key in tui.keybindings["word_left"] or next_key == ord('b'):
                    end = self._word_backward(buf, end)
                elif next_key == ord('e'):
                    end = self._word_end(buf, end)
                else:
                    break
            if next_key == ord('$'):
                end = len(buf)
            elif next_key == ord('^'):
                end = 0
                while end < len(buf) and buf[end] == ' ':
                    end += 1
            if end != start:
                lo, hi = min(start, end), max(start, end)
                tui.input_buffer = buf[:lo] + buf[hi:]
                self._apply_input_motion(tui, lo)
            return _VIM_SCROLL_CODE

        elif key == ord('x') and not tui.insert_mode:
            buf = tui.input_buffer
            idx = tui.input_index
            if idx < len(buf):
                end = min(idx + count, len(buf))
                tui.input_buffer = buf[:idx] + buf[end:]
                self._apply_input_motion(tui, min(idx, len(tui.input_buffer)))
            return _VIM_SCROLL_CODE

        elif key == ord('a') and not tui.insert_mode:
            if tui.input_index >= len(tui.input_buffer):
                tui.input_buffer += ' '
            idx = min(tui.input_index + 1, len(tui.input_buffer))
            self._apply_input_motion(tui, idx)
            tui.insert_mode = True
            return 28

        elif key == _CTRL_U and not tui.insert_mode:
            half = tui.chat_hw[0] // 2
            if tui.chat_selected < 0:
                tui.chat_selected = 0
            delta = min(half, len(tui.chat_buffer) - 1 - tui.chat_selected)
            if delta > 0:
                tui.chat_selected += delta
                tui.chat_index = min(tui.chat_index + delta, len(tui.chat_buffer) - tui.chat_hw[0] + 2)
                tui.chat_index = max(tui.chat_index, 0)
                self._skip_image_placeholders(tui, +1)
                tui.draw_chat()
            return _VIM_SCROLL_CODE

        elif key == _CTRL_D and not tui.insert_mode:
            half = tui.chat_hw[0] // 2
            if tui.chat_selected > 0:
                delta = min(half, tui.chat_selected)
                tui.chat_selected -= delta
                tui.chat_index = max(tui.chat_index - delta, 0)
                self._skip_image_placeholders(tui, -1)
                tui.draw_chat()
            return _VIM_SCROLL_CODE

        elif key in tui.keybindings["quit"]:
            return 34

        else:
            ext_ret = tui.execute_extensions_method_first("on_binding", key, command, forum, cache=True)
            if isinstance(ext_ret, int):
                return ext_ret

        return None
