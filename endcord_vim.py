# Copyright (C) 2025-2026 Dylan Simon
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.

"""Adds count-prefix vim navigation: type a number then j/k/J/K to move N steps."""

import logging

EXT_NAME = "Vim Count Navigation"
EXT_VERSION = "0.1.0"
EXT_ENDCORD_VERSION = "1.4.2"
EXT_DESCRIPTION = "Count-prefix vim navigation: type a number before j/k (chat) or J/K (channel tree) to move N steps."
EXT_SOURCE = "https://github.com/ghidbase/endcord-vim"

logger = logging.getLogger(__name__)

_VIM_DIGIT_CODE = 1001   # action code returned when a digit is absorbed into vim_count


class Extension:
    def __init__(self, app):
        self.app = app
        app.tui.vim_count = 0
        app.tui.common_keybindings = self._common_keybindings
        logger.info("Vim count navigation active")

    def on_binding(self, key, is_command, is_forum):
        """Absorb digit keypresses in normal mode into vim_count."""
        tui = self.app.tui
        if (not tui.insert_mode
                and tui.switch_tab_modifier
                and isinstance(key, int)
                and ((49 <= key <= 57) or (key == 48 and tui.vim_count > 0))):
            tui.vim_count = min(tui.vim_count * 10 + (key - 48), 999)
            return _VIM_DIGIT_CODE

    def on_escape_key(self):
        self.app.tui.vim_count = 0

    def on_wait_input(self, action_code, input_text, chat_sel, tree_sel):
        """Keep the input loop running after a digit is absorbed."""
        if action_code == _VIM_DIGIT_CODE:
            self.restore_input_text = (input_text, "standard")
            return True

    def _common_keybindings(self, key, mouse=False, switch=False, command=False, forum=False):
        """Replacement for tui.common_keybindings that reads vim_count at the top."""
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
                    if top_line < tui.member_list and tui.mlist_selected >= top_line - 1:
                        tui.mlist_index += 1
                    tui.mlist_selected += 1
                    tui.draw_member_list(tui.member_list, tui.member_list_format)

        elif key in tui.keybindings["quit"]:
            return 34

        else:
            ext_ret = tui.execute_extensions_method_first("on_binding", key, command, forum, cache=True)
            if isinstance(ext_ret, int):
                return ext_ret

        return None
