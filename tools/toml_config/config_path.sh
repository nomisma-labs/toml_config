#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

# Source this file from ~/.bash_aliases to select config directories in this shell.
# Definitions alone do not change NOM_CONFIG_DIR.

cfg_set() {
    if (( $# != 0 )); then
        printf 'Usage: cfg_set (uses the current directory)\n' >&2
        return 2
    fi

    local config_dir
    # Keep trailing newlines in directory names through command substitution.
    config_dir=$(builtin pwd -P && printf '.') || return
    config_dir=${config_dir%$'\n.'}
    if [[ $config_dir == *:* ]]; then
        printf 'cfg_set: directory names containing ":" cannot be used in NOM_CONFIG_DIR\n' >&2
        return 1
    fi

    export NOM_CONFIG_DIR="$config_dir" || return
    cfg_print
}

cfg_add() {
    if (( $# != 0 )); then
        printf 'Usage: cfg_add (uses the current directory)\n' >&2
        return 2
    fi

    if [[ -z ${NOM_CONFIG_DIR-} ]]; then
        cfg_set
        return
    fi
    if [[ $NOM_CONFIG_DIR == :* || $NOM_CONFIG_DIR == *: || $NOM_CONFIG_DIR == *::* ]]; then
        printf 'cfg_add: NOM_CONFIG_DIR contains an empty entry; use cfg_set to replace it\n' >&2
        return 1
    fi

    local config_dir
    config_dir=$(builtin pwd -P && printf '.') || return
    config_dir=${config_dir%$'\n.'}
    if [[ $config_dir == *:* ]]; then
        printf 'cfg_add: directory names containing ":" cannot be used in NOM_CONFIG_DIR\n' >&2
        return 1
    fi

    if [[ ":$NOM_CONFIG_DIR:" != *":$config_dir:"* ]]; then
        NOM_CONFIG_DIR+=":$config_dir"
    fi
    export NOM_CONFIG_DIR || return
    cfg_print
}

cfg_clear() {
    if (( $# != 0 )); then
        printf 'Usage: cfg_clear\n' >&2
        return 2
    fi

    unset -v NOM_CONFIG_DIR || return
    cfg_print
}

cfg_print() {
    if (( $# != 0 )); then
        printf 'Usage: cfg_print\n' >&2
        return 2
    fi

    if [[ ! ${NOM_CONFIG_DIR+x} ]]; then
        printf 'NOM_CONFIG_DIR is not set\n'
    elif [[ -z $NOM_CONFIG_DIR ]]; then
        printf 'NOM_CONFIG_DIR is empty\n'
    else
        printf '%s\n' "${NOM_CONFIG_DIR//:/$'\n'}"
    fi
}
